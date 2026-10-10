<?php
/**
 * Admin authentication: password + TOTP (Google Authenticator) + one-time recovery codes,
 * hardened sessions, CSRF tokens and login lockout.
 */
if (!defined('APF_SERVER')) { http_response_code(403); exit; }

const APF_SESSION_IDLE = 1800;      // 30 min without activity -> logout
const APF_SESSION_MAX = 43200;      // 12 h absolute
const APF_LOGIN_MAX_FAILS = 5;      // per IP per 15 min
const APF_LOGIN_GLOBAL_FAILS = 30;  // all IPs per hour (stops distributed guessing)

function apf_session_start() {
    if (session_status() === PHP_SESSION_ACTIVE) return;
    session_name('APFADMIN');
    // Path "/" so the album server admin page on the same domain can reuse this login
    session_set_cookie_params([
        'lifetime' => 0, 'path' => '/', 'secure' => apf_is_https(), 'httponly' => true, 'samesite' => 'Strict',
    ]);
    ini_set('session.use_strict_mode', '1');
    ini_set('session.use_only_cookies', '1');
    session_start();
}

function apf_admin() {
    apf_session_start();
    if (empty($_SESSION['apf_admin_id'])) return null;
    $now = time();
    $fp = hash('sha256', ($_SERVER['HTTP_USER_AGENT'] ?? '') . '|' . APF_PUBLIC_KEY_B64);
    if (($_SESSION['apf_fp'] ?? '') !== $fp
        || $now - (int)($_SESSION['apf_last'] ?? 0) > APF_SESSION_IDLE
        || $now - (int)($_SESSION['apf_started'] ?? 0) > APF_SESSION_MAX) {
        apf_logout();
        return null;
    }
    $_SESSION['apf_last'] = $now;
    $st = apf_db()->prepare('SELECT * FROM admins WHERE id = ?');
    $st->execute([$_SESSION['apf_admin_id']]);
    return $st->fetch() ?: null;
}

function apf_login_session(array $admin) {
    apf_session_start();
    session_regenerate_id(true);
    $_SESSION['apf_admin_id'] = (int)$admin['id'];
    $_SESSION['apf_admin'] = 1;
    $_SESSION['apf_started'] = time();
    $_SESSION['apf_last'] = time();
    $_SESSION['apf_fp'] = hash('sha256', ($_SERVER['HTTP_USER_AGENT'] ?? '') . '|' . APF_PUBLIC_KEY_B64);
    $_SESSION['apf_csrf'] = bin2hex(random_bytes(32));
}

function apf_logout() {
    apf_session_start();
    $_SESSION = [];
    if (ini_get('session.use_cookies')) {
        $p = session_get_cookie_params();
        setcookie(session_name(), '', time() - 3600, $p['path'], $p['domain'] ?? '', $p['secure'], $p['httponly']);
    }
    session_destroy();
}

function apf_csrf_token() {
    apf_session_start();
    if (empty($_SESSION['apf_csrf'])) $_SESSION['apf_csrf'] = bin2hex(random_bytes(32));
    return $_SESSION['apf_csrf'];
}

function apf_csrf_field() { return '<input type="hidden" name="csrf" value="' . h(apf_csrf_token()) . '">'; }

function apf_csrf_check() {
    apf_session_start();
    $sent = $_POST['csrf'] ?? '';
    if (!$sent || empty($_SESSION['apf_csrf']) || !hash_equals($_SESSION['apf_csrf'], $sent)) {
        http_response_code(400);
        exit('Security token expired. Go back, reload the page and try again.');
    }
}

// ---------------- TOTP (RFC 6238, SHA1, 30 s, 6 digits) ----------------
function apf_base32_encode($bin) {
    $alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
    $bits = '';
    foreach (str_split($bin) as $c) $bits .= str_pad(decbin(ord($c)), 8, '0', STR_PAD_LEFT);
    $out = '';
    foreach (str_split($bits, 5) as $chunk) $out .= $alphabet[bindec(str_pad($chunk, 5, '0'))];
    return $out;
}

function apf_base32_decode($s) {
    $alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
    $s = strtoupper(preg_replace('/[^A-Za-z2-7]/', '', $s));
    $bits = '';
    foreach (str_split($s) as $c) $bits .= str_pad(decbin(strpos($alphabet, $c)), 5, '0', STR_PAD_LEFT);
    $out = '';
    foreach (str_split($bits, 8) as $byte) if (strlen($byte) === 8) $out .= chr(bindec($byte));
    return $out;
}

function apf_totp_at($secretB32, $step) {
    $key = apf_base32_decode($secretB32);
    $msg = pack('N2', 0, $step);
    $hash = hash_hmac('sha1', $msg, $key, true);
    $off = ord($hash[19]) & 0x0f;
    $num = ((ord($hash[$off]) & 0x7f) << 24) | (ord($hash[$off + 1]) << 16) | (ord($hash[$off + 2]) << 8) | ord($hash[$off + 3]);
    return str_pad((string)($num % 1000000), 6, '0', STR_PAD_LEFT);
}

/** Returns the matched time step, or 0. Allows +-1 step clock drift. */
function apf_totp_verify($secretB32, $code, $lastStep = 0) {
    $code = preg_replace('/\D/', '', (string)$code);
    if (strlen($code) !== 6) return 0;
    $now = (int)floor(time() / 30);
    for ($d = -1; $d <= 1; $d++) {
        $step = $now + $d;
        if ($step <= (int)$lastStep) continue;  // each code works only once
        if (hash_equals(apf_totp_at($secretB32, $step), $code)) return $step;
    }
    return 0;
}

function apf_new_recovery_codes() {
    $plain = [];
    for ($i = 0; $i < 8; $i++) $plain[] = strtoupper(bin2hex(random_bytes(2)) . '-' . bin2hex(random_bytes(2)) . '-' . bin2hex(random_bytes(2)));
    $hashes = array_map(function ($c) { return password_hash($c, PASSWORD_DEFAULT); }, $plain);
    return [$plain, json_encode($hashes)];
}

/** Uses up a recovery code. Returns true when it matched. */
function apf_use_recovery_code(array $admin, $code) {
    $code = strtoupper(trim($code));
    $hashes = json_decode($admin['recovery_codes'] ?: '[]', true) ?: [];
    foreach ($hashes as $i => $hsh) {
        if (password_verify($code, $hsh)) {
            unset($hashes[$i]);
            apf_db()->prepare('UPDATE admins SET recovery_codes = ? WHERE id = ?')->execute([json_encode(array_values($hashes)), $admin['id']]);
            return true;
        }
    }
    return false;
}

function apf_password_problem($pw) {
    if (strlen($pw) < 12) return 'Password must be at least 12 characters.';
    if (!preg_match('/[A-Z]/', $pw) || !preg_match('/[a-z]/', $pw) || !preg_match('/\d/', $pw) || !preg_match('/[^A-Za-z0-9]/', $pw)) {
        return 'Password needs upper case, lower case, a number and a symbol.';
    }
    return null;
}

function apf_login_locked() {
    $ip = apf_ip();
    return apf_rate_count('login:' . $ip, 900) >= APF_LOGIN_MAX_FAILS
        || apf_rate_count('login:all', 3600) >= APF_LOGIN_GLOBAL_FAILS;
}

function apf_login_failed($username) {
    apf_rate_limit('login:' . apf_ip(), APF_LOGIN_MAX_FAILS, 900);
    apf_rate_limit('login:all', APF_LOGIN_GLOBAL_FAILS, 3600);
    apf_audit('login', 'login_failed', ['username' => mb_substr((string)$username, 0, 60)]);
    usleep(random_int(400000, 900000));
}
