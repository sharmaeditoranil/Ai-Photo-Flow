<?php
/**
 * Ai PhotoFlow License Server - core library.
 * Database, settings, Ed25519 license signing, rate limiting and helpers.
 * Compatible with PHP 7.4 - 8.x (needs pdo_sqlite, sodium, curl).
 */
if (!defined('APF_SERVER')) { http_response_code(403); exit; }

// Never print PHP warnings / paths to visitors; they go to the server error log instead
ini_set('display_errors', '0');
ini_set('log_errors', '1');

require_once __DIR__ . '/../config.php';

const APF_PLANS = ['PRO', 'STUDIO', 'VIP_LIFETIME'];
const APF_CYCLES = ['monthly' => 30, 'yearly' => 365, 'lifetime' => null];

// ------------------------------------------------------------------
// Private data directory (outside public_html whenever possible)
// ------------------------------------------------------------------
function apf_data_dir() {
    static $dir = null;
    if ($dir !== null) return $dir;
    $candidates = [];
    if (defined('APF_DATA_DIR') && APF_DATA_DIR) $candidates[] = APF_DATA_DIR;
    $docRoot = isset($_SERVER['DOCUMENT_ROOT']) ? rtrim($_SERVER['DOCUMENT_ROOT'], '/') : '';
    if ($docRoot) $candidates[] = dirname($docRoot) . '/apf_license_private';
    $candidates[] = dirname(__DIR__) . '/data_' . substr(hash('sha256', APF_SECRET_KEY_B64), 0, 16);
    foreach ($candidates as $c) {
        if (!is_dir($c)) @mkdir($c, 0700, true);
        if (is_dir($c) && is_writable($c)) {
            // Belt and braces in case the folder is inside the web root
            if (!file_exists($c . '/.htaccess')) @file_put_contents($c . '/.htaccess',
                "<IfModule mod_authz_core.c>\nRequire all denied\n</IfModule>\n<IfModule !mod_authz_core.c>\nDeny from all\n</IfModule>\n");
            if (!file_exists($c . '/index.html')) @file_put_contents($c . '/index.html', '');
            $dir = $c;
            return $dir;
        }
    }
    http_response_code(500);
    exit('License server: no writable private data folder.');
}

function apf_db() {
    static $pdo = null;
    if ($pdo) return $pdo;
    $pdo = new PDO('sqlite:' . apf_data_dir() . '/license.sqlite');
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
    $pdo->exec('PRAGMA journal_mode = WAL');
    $pdo->exec('PRAGMA busy_timeout = 5000');
    $pdo->exec('PRAGMA foreign_keys = ON');
    apf_schema($pdo);
    return $pdo;
}

function apf_schema(PDO $db) {
    $db->exec("
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, pass_hash TEXT NOT NULL,
        totp_secret TEXT NOT NULL, totp_last_step INTEGER DEFAULT 0, recovery_codes TEXT DEFAULT '[]',
        created_at INTEGER NOT NULL, last_login_at INTEGER, last_login_ip TEXT);
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS agents (
        id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT DEFAULT '', email TEXT DEFAULT '',
        commission_percent REAL NOT NULL DEFAULT 20, payout_upi TEXT DEFAULT '', payout_bank TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'ACTIVE', notes TEXT DEFAULT '', created_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS coupons (
        code TEXT PRIMARY KEY, discount_percent REAL NOT NULL, max_uses INTEGER DEFAULT 0, used_count INTEGER DEFAULT 0,
        valid_until INTEGER, plans TEXT DEFAULT '', agent_id INTEGER REFERENCES agents(id) ON DELETE SET NULL,
        active INTEGER NOT NULL DEFAULT 1, notes TEXT DEFAULT '', created_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS licenses (
        id INTEGER PRIMARY KEY, license_key TEXT UNIQUE NOT NULL, plan TEXT NOT NULL, cycle TEXT NOT NULL,
        max_devices INTEGER NOT NULL, expires_at INTEGER, status TEXT NOT NULL DEFAULT 'ACTIVE',
        customer_name TEXT DEFAULT '', customer_email TEXT DEFAULT '', customer_phone TEXT DEFAULT '',
        source TEXT NOT NULL DEFAULT 'MANUAL', order_id TEXT, agent_id INTEGER REFERENCES agents(id) ON DELETE SET NULL,
        notes TEXT DEFAULT '', created_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS activations (
        id INTEGER PRIMARY KEY, license_id INTEGER NOT NULL REFERENCES licenses(id) ON DELETE CASCADE,
        machine_id TEXT NOT NULL, machine_name TEXT DEFAULT '', os TEXT DEFAULT '', app_version TEXT DEFAULT '',
        first_seen INTEGER NOT NULL, last_seen INTEGER NOT NULL, last_ip TEXT DEFAULT '', active INTEGER NOT NULL DEFAULT 1,
        UNIQUE(license_id, machine_id));
    CREATE TABLE IF NOT EXISTS trials (
        machine_id TEXT PRIMARY KEY, started_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
        last_seen INTEGER NOT NULL, os TEXT DEFAULT '', machine_name TEXT DEFAULT '', last_ip TEXT DEFAULT '',
        blocked INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY, order_id TEXT UNIQUE NOT NULL, plan TEXT NOT NULL, cycle TEXT NOT NULL,
        currency TEXT NOT NULL, base_amount REAL NOT NULL, amount REAL NOT NULL, coupon TEXT DEFAULT '',
        agent_id INTEGER, customer_name TEXT DEFAULT '', customer_email TEXT DEFAULT '', customer_phone TEXT DEFAULT '',
        machine_id TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'CREATED', payment_id TEXT DEFAULT '',
        license_id INTEGER, created_at INTEGER NOT NULL, paid_at INTEGER, last_ip TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS commissions (
        id INTEGER PRIMARY KEY, order_id TEXT UNIQUE NOT NULL, agent_id INTEGER NOT NULL REFERENCES agents(id),
        sale_amount REAL NOT NULL, rate REAL NOT NULL, amount REAL NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING',
        payout_ref TEXT DEFAULT '', paid_at INTEGER, created_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY, ts INTEGER NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
        details TEXT DEFAULT '', ip TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS rate_limits (bucket TEXT PRIMARY KEY, window_start INTEGER NOT NULL, hits INTEGER NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_act_license ON activations(license_id);
    CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
    CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);
    ");
}

// ------------------------------------------------------------------
// Settings
// ------------------------------------------------------------------
function apf_default_settings() {
    return [
        'prices' => json_encode([
            'INR' => ['PRO' => ['monthly' => 499, 'yearly' => 3499], 'STUDIO' => ['monthly' => 999, 'yearly' => 6999]],
            'USD' => ['PRO' => ['monthly' => 7, 'yearly' => 45], 'STUDIO' => ['monthly' => 14, 'yearly' => 89]],
        ]),
        'devices' => json_encode(['PRO' => 1, 'STUDIO' => 3, 'VIP_LIFETIME' => 3]),
        'trial_days' => '3',
        'offline_grace_days' => '30',
        'payments_enabled' => '1',
        'razorpay_key_id' => '',
        'razorpay_key_secret' => '',
        'razorpay_webhook_secret' => '',
        'business_name' => 'Ai PhotoFlow',
    ];
}

function apf_setting($key) {
    $st = apf_db()->prepare('SELECT value FROM settings WHERE key = ?');
    $st->execute([$key]);
    $v = $st->fetchColumn();
    if ($v === false) {
        $d = apf_default_settings();
        return isset($d[$key]) ? $d[$key] : '';
    }
    return $v;
}

function apf_set_setting($key, $value) {
    $st = apf_db()->prepare('INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value');
    $st->execute([$key, (string)$value]);
}

function apf_prices() { return json_decode(apf_setting('prices'), true) ?: json_decode(apf_default_settings()['prices'], true); }
function apf_devices() { return json_decode(apf_setting('devices'), true) ?: json_decode(apf_default_settings()['devices'], true); }

// ------------------------------------------------------------------
// Helpers
// ------------------------------------------------------------------
function h($s) { return htmlspecialchars((string)$s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }

function apf_ip() {
    // Hostinger / LiteSpeed pass the real client address in REMOTE_ADDR; never trust X-Forwarded-For blindly
    return isset($_SERVER['REMOTE_ADDR']) ? substr($_SERVER['REMOTE_ADDR'], 0, 64) : '';
}

function apf_is_https() {
    if (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') return true;
    if (isset($_SERVER['SERVER_PORT']) && (int)$_SERVER['SERVER_PORT'] === 443) return true;
    if (isset($_SERVER['HTTP_X_FORWARDED_PROTO']) && strtolower($_SERVER['HTTP_X_FORWARDED_PROTO']) === 'https') return true;
    return false;
}

function apf_is_local() {
    $host = isset($_SERVER['HTTP_HOST']) ? strtolower(preg_replace('/:\d+$/', '', $_SERVER['HTTP_HOST'])) : '';
    return in_array($host, ['localhost', '127.0.0.1'], true);
}

function apf_require_https() {
    if (!apf_is_https() && !apf_is_local()) {
        $url = 'https://' . $_SERVER['HTTP_HOST'] . $_SERVER['REQUEST_URI'];
        header('Location: ' . $url, true, 301);
        exit;
    }
}

function apf_audit($actor, $action, $details = '') {
    $st = apf_db()->prepare('INSERT INTO audit_log (ts, actor, action, details, ip) VALUES (?, ?, ?, ?, ?)');
    $st->execute([time(), $actor, $action, is_string($details) ? $details : json_encode($details), apf_ip()]);
}

/** Fixed-window rate limit. Returns true if the call is allowed. */
function apf_rate_limit($bucket, $max, $windowSeconds) {
    $db = apf_db();
    $now = time();
    $db->beginTransaction();
    $st = $db->prepare('SELECT window_start, hits FROM rate_limits WHERE bucket = ?');
    $st->execute([$bucket]);
    $row = $st->fetch();
    if (!$row || $now - (int)$row['window_start'] >= $windowSeconds) {
        $db->prepare('INSERT INTO rate_limits (bucket, window_start, hits) VALUES (?, ?, 1)
                      ON CONFLICT(bucket) DO UPDATE SET window_start = excluded.window_start, hits = 1')->execute([$bucket, $now]);
        $db->commit();
        return true;
    }
    $hits = (int)$row['hits'] + 1;
    $db->prepare('UPDATE rate_limits SET hits = ? WHERE bucket = ?')->execute([$hits, $bucket]);
    $db->commit();
    if (mt_rand(1, 200) === 1) $db->prepare('DELETE FROM rate_limits WHERE window_start < ?')->execute([$now - 86400]);
    return $hits <= $max;
}

function apf_rate_count($bucket, $windowSeconds) {
    $st = apf_db()->prepare('SELECT window_start, hits FROM rate_limits WHERE bucket = ?');
    $st->execute([$bucket]);
    $row = $st->fetch();
    if (!$row || time() - (int)$row['window_start'] >= $windowSeconds) return 0;
    return (int)$row['hits'];
}

function apf_new_license_key() {
    $alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // no 0/O/1/I
    $groups = [];
    for ($g = 0; $g < 4; $g++) {
        $s = '';
        for ($i = 0; $i < 5; $i++) $s .= $alphabet[random_int(0, strlen($alphabet) - 1)];
        $groups[] = $s;
    }
    return 'APF-' . implode('-', $groups);
}

function apf_clean_key($k) { return strtoupper(preg_replace('/[^A-Za-z0-9\-]/', '', (string)$k)); }
function apf_clean_machine($m) { return substr(preg_replace('/[^A-Za-z0-9\-]/', '', (string)$m), 0, 64); }
function apf_str($s, $max = 200) { return mb_substr(trim((string)$s), 0, $max); }

function apf_money($amount, $currency = 'INR') {
    $sym = $currency === 'USD' ? '$' : '₹';
    return $sym . number_format((float)$amount, ($amount == floor($amount)) ? 0 : 2);
}

function apf_date($ts) { return $ts ? date('d M Y, H:i', (int)$ts) : '—'; }

// ------------------------------------------------------------------
// License tokens (Ed25519). The app only has the public key, so tokens cannot be forged.
// ------------------------------------------------------------------
function apf_b64url($s) { return rtrim(strtr(base64_encode($s), '+/', '-_'), '='); }

/** Ed25519 via PHP's sodium extension, or the bundled pure-PHP sodium_compat (ISC) when the host has it switched off. */
function apf_use_compat() {
    static $compat = null;
    if ($compat === null) {
        $compat = defined('APF_FORCE_SODIUM_COMPAT') || !function_exists('sodium_crypto_sign_detached');
        if ($compat) {
            require_once __DIR__ . '/sodium_compat/autoload.php';
            // Always use the pure-PHP code path here: the native functions are not available on this host
            ParagonIE_Sodium_Compat::$disableFallbackForUnitTests = true;
        }
    }
    return $compat;
}

function apf_ed_sign($message, $secretKey) {
    return apf_use_compat() ? ParagonIE_Sodium_Compat::crypto_sign_detached($message, $secretKey)
                            : sodium_crypto_sign_detached($message, $secretKey);
}

function apf_ed_verify($signature, $message, $publicKey) {
    try {
        return apf_use_compat() ? ParagonIE_Sodium_Compat::crypto_sign_verify_detached($signature, $message, $publicKey)
                                : sodium_crypto_sign_verify_detached($signature, $message, $publicKey);
    } catch (Throwable $e) {
        return false;
    }
}

function apf_sign_token(array $payload) {
    $body = apf_b64url(json_encode($payload, JSON_UNESCAPED_SLASHES));
    $sig = apf_ed_sign($body, base64_decode(APF_SECRET_KEY_B64));
    return $body . '.' . apf_b64url($sig);
}

function apf_verify_token($token) {
    $parts = explode('.', (string)$token);
    if (count($parts) !== 2) return null;
    $sig = base64_decode(strtr($parts[1], '-_', '+/'));
    if ($sig === false || strlen($sig) !== 64) return null;
    if (!apf_ed_verify($sig, $parts[0], base64_decode(APF_PUBLIC_KEY_B64))) return null;
    $json = base64_decode(strtr($parts[0], '-_', '+/'));
    $data = json_decode($json, true);
    return is_array($data) ? $data : null;
}

function apf_license_token(array $lic, $machineId) {
    $now = time();
    $grace = max(1, (int)apf_setting('offline_grace_days')) * 86400;
    $rby = $now + $grace;
    if ($lic['expires_at']) $rby = min($rby, (int)$lic['expires_at']);
    return apf_sign_token([
        'v' => 1, 'typ' => 'license', 'lic' => $lic['license_key'], 'plan' => $lic['plan'],
        'mid' => $machineId, 'dev' => (int)$lic['max_devices'],
        'exp' => $lic['expires_at'] ? (int)$lic['expires_at'] : null,
        'iat' => $now, 'rby' => $rby, 'act' => (int)$lic['created_at'],
        'name' => $lic['customer_name'], 'email' => $lic['customer_email'], 'phone' => $lic['customer_phone'],
    ]);
}

function apf_trial_token(array $trial) {
    $now = time();
    $grace = max(1, (int)apf_setting('offline_grace_days')) * 86400;
    return apf_sign_token([
        'v' => 1, 'typ' => 'trial', 'lic' => null, 'plan' => 'FREE_TRIAL',
        'mid' => $trial['machine_id'], 'dev' => 1, 'exp' => (int)$trial['expires_at'],
        'iat' => $now, 'rby' => min($now + $grace, (int)$trial['expires_at']), 'act' => (int)$trial['started_at'],
        'name' => '', 'email' => '', 'phone' => '',
    ]);
}

// ------------------------------------------------------------------
// Licensing operations shared by API and admin panel
// ------------------------------------------------------------------
function apf_get_license_by_key($key) {
    $st = apf_db()->prepare('SELECT * FROM licenses WHERE license_key = ?');
    $st->execute([apf_clean_key($key)]);
    return $st->fetch() ?: null;
}

function apf_license_state(array $lic) {
    if ($lic['status'] !== 'ACTIVE') return $lic['status'];           // REVOKED / SUSPENDED
    if ($lic['expires_at'] && (int)$lic['expires_at'] < time()) return 'EXPIRED';
    return 'ACTIVE';
}

function apf_create_license(array $o) {
    $db = apf_db();
    $plan = in_array($o['plan'], APF_PLANS, true) ? $o['plan'] : 'PRO';
    $cycle = array_key_exists($o['cycle'], APF_CYCLES) ? $o['cycle'] : 'yearly';
    if ($plan === 'VIP_LIFETIME') $cycle = 'lifetime';
    $days = isset($o['days']) && $o['days'] !== null && $o['days'] !== '' ? (int)$o['days'] : APF_CYCLES[$cycle];
    $devices = isset($o['max_devices']) && (int)$o['max_devices'] > 0 ? (int)$o['max_devices'] : (int)(apf_devices()[$plan] ?? 1);
    for ($i = 0; $i < 5; $i++) {
        $key = apf_new_license_key();
        try {
            $db->prepare('INSERT INTO licenses (license_key, plan, cycle, max_devices, expires_at, status, customer_name,
                customer_email, customer_phone, source, order_id, agent_id, notes, created_at)
                VALUES (?, ?, ?, ?, ?, \'ACTIVE\', ?, ?, ?, ?, ?, ?, ?, ?)')
               ->execute([$key, $plan, $cycle, $devices, $days ? time() + $days * 86400 : null,
                          apf_str($o['customer_name'] ?? ''), apf_str($o['customer_email'] ?? ''), apf_str($o['customer_phone'] ?? '', 40),
                          $o['source'] ?? 'MANUAL', $o['order_id'] ?? null, $o['agent_id'] ?? null, apf_str($o['notes'] ?? '', 1000), time()]);
            $st = $db->prepare('SELECT * FROM licenses WHERE id = ?');
            $st->execute([$db->lastInsertId()]);
            return $st->fetch();
        } catch (PDOException $e) {
            if ($i === 4) throw $e; // astronomically unlikely key collision, retry
        }
    }
    return null;
}

/** Binds a machine to a license (respecting the device limit). Returns [ok, errorCode, message]. */
function apf_activate_machine(array $lic, $machineId, $machineName = '', $os = '', $appVersion = '') {
    $db = apf_db();
    $now = time();
    $st = $db->prepare('SELECT * FROM activations WHERE license_id = ? AND machine_id = ?');
    $st->execute([$lic['id'], $machineId]);
    $act = $st->fetch();
    if ($act && (int)$act['active'] === 1) {
        $db->prepare('UPDATE activations SET last_seen = ?, last_ip = ?, os = ?, machine_name = ?, app_version = ? WHERE id = ?')
           ->execute([$now, apf_ip(), apf_str($os, 60), apf_str($machineName, 80), apf_str($appVersion, 20), $act['id']]);
        return [true, null, 'ok'];
    }
    $st = $db->prepare('SELECT COUNT(*) FROM activations WHERE license_id = ? AND active = 1');
    $st->execute([$lic['id']]);
    if ((int)$st->fetchColumn() >= (int)$lic['max_devices']) {
        return [false, 'DEVICE_LIMIT', 'This license is already active on ' . (int)$lic['max_devices'] .
            ' computer(s). Deactivate it on the old computer first, or contact support.'];
    }
    if ($act) {
        $db->prepare('UPDATE activations SET active = 1, last_seen = ?, last_ip = ?, os = ?, machine_name = ? WHERE id = ?')
           ->execute([$now, apf_ip(), apf_str($os, 60), apf_str($machineName, 80), $act['id']]);
    } else {
        $db->prepare('INSERT INTO activations (license_id, machine_id, machine_name, os, app_version, first_seen, last_seen, last_ip, active)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)')
           ->execute([$lic['id'], $machineId, apf_str($machineName, 80), apf_str($os, 60), apf_str($appVersion, 20), $now, $now, apf_ip()]);
    }
    apf_audit('app', 'activate', ['license' => $lic['license_key'], 'machine' => $machineId, 'name' => $machineName]);
    return [true, null, 'ok'];
}

function apf_public_license(array $lic) {
    return [
        'plan' => $lic['plan'], 'cycle' => $lic['cycle'], 'max_devices' => (int)$lic['max_devices'],
        'expires_at' => $lic['expires_at'] ? (int)$lic['expires_at'] : null, 'status' => apf_license_state($lic),
        'customer_name' => $lic['customer_name'], 'customer_email' => $lic['customer_email'],
        'customer_phone' => $lic['customer_phone'], 'license_key' => $lic['license_key'],
        'activated_at' => (int)$lic['created_at'],
    ];
}

// ------------------------------------------------------------------
// Pricing, coupons and orders
// ------------------------------------------------------------------
function apf_base_price($plan, $cycle, $currency) {
    $p = apf_prices();
    if (!isset($p[$currency][$plan][$cycle])) return null;
    return (float)$p[$currency][$plan][$cycle];
}

/** Returns [couponRow|null, errorMessage|null]. */
function apf_check_coupon($code, $plan) {
    $code = strtoupper(preg_replace('/[^A-Za-z0-9_\-]/', '', (string)$code));
    if ($code === '') return [null, null];
    $st = apf_db()->prepare('SELECT * FROM coupons WHERE code = ?');
    $st->execute([$code]);
    $c = $st->fetch();
    if (!$c || !(int)$c['active']) return [null, 'Invalid or expired coupon code'];
    if ($c['valid_until'] && (int)$c['valid_until'] < time()) return [null, 'This coupon has expired'];
    if ((int)$c['max_uses'] > 0 && (int)$c['used_count'] >= (int)$c['max_uses']) return [null, 'This coupon has reached its usage limit'];
    if ($c['plans'] !== '' && !in_array($plan, explode(',', $c['plans']), true)) return [null, 'This coupon is not valid for the ' . $plan . ' plan'];
    if ($c['agent_id']) {
        $st = apf_db()->prepare("SELECT status FROM agents WHERE id = ?");
        $st->execute([$c['agent_id']]);
        if ($st->fetchColumn() !== 'ACTIVE') return [null, 'This referral code is no longer active'];
    }
    return [$c, null];
}

function apf_quote($plan, $cycle, $currency, $couponCode) {
    $base = apf_base_price($plan, $cycle, $currency);
    if ($base === null) return ['ok' => false, 'error' => 'Invalid plan or billing cycle'];
    list($coupon, $err) = apf_check_coupon($couponCode, $plan);
    if ($err) return ['ok' => false, 'error' => $err];
    $pct = $coupon ? (float)$coupon['discount_percent'] : 0.0;
    $discount = $currency === 'INR' ? round($base * $pct / 100) : round($base * $pct / 100, 2);
    $final = max(0, $base - $discount);
    return ['ok' => true, 'plan' => $plan, 'cycle' => $cycle, 'currency' => $currency, 'original_price' => $base,
            'discount_percent' => $pct, 'discount_amount' => $discount, 'final_price' => $final,
            'coupon' => $coupon ? $coupon['code'] : '', 'agent_id' => $coupon ? $coupon['agent_id'] : null];
}

/** Marks an order paid exactly once and creates its license, coupon usage and commission. */
function apf_fulfill_order($orderId, $paymentId, $actor) {
    $db = apf_db();
    $db->beginTransaction();
    try {
        $st = $db->prepare('SELECT * FROM orders WHERE order_id = ?');
        $st->execute([$orderId]);
        $o = $st->fetch();
        if (!$o) { $db->rollBack(); return null; }
        if ($o['status'] === 'PAID' && $o['license_id']) {
            $db->commit();
            $st = $db->prepare('SELECT * FROM licenses WHERE id = ?');
            $st->execute([$o['license_id']]);
            return $st->fetch();
        }
        $lic = apf_create_license([
            'plan' => $o['plan'], 'cycle' => $o['cycle'], 'customer_name' => $o['customer_name'],
            'customer_email' => $o['customer_email'], 'customer_phone' => $o['customer_phone'],
            'source' => 'PAYMENT', 'order_id' => $o['order_id'], 'agent_id' => $o['agent_id'],
        ]);
        $db->prepare("UPDATE orders SET status = 'PAID', payment_id = ?, license_id = ?, paid_at = ? WHERE id = ?")
           ->execute([apf_str($paymentId, 80), $lic['id'], time(), $o['id']]);
        if ($o['coupon'] !== '') {
            $db->prepare('UPDATE coupons SET used_count = used_count + 1 WHERE code = ?')->execute([$o['coupon']]);
        }
        if ($o['agent_id'] && (float)$o['amount'] > 0) {
            $st = $db->prepare('SELECT commission_percent FROM agents WHERE id = ?');
            $st->execute([$o['agent_id']]);
            $rate = (float)$st->fetchColumn();
            $db->prepare('INSERT OR IGNORE INTO commissions (order_id, agent_id, sale_amount, rate, amount, status, created_at)
                          VALUES (?, ?, ?, ?, ?, \'PENDING\', ?)')
               ->execute([$o['order_id'], $o['agent_id'], $o['amount'], $rate, round($o['amount'] * $rate / 100, 2), time()]);
        }
        $db->commit();
        apf_audit($actor, 'order_paid', ['order' => $o['order_id'], 'payment' => $paymentId, 'amount' => $o['amount'],
                                         'license' => $lic['license_key']]);
        return $lic;
    } catch (Exception $e) {
        if ($db->inTransaction()) $db->rollBack();
        throw $e;
    }
}

// ------------------------------------------------------------------
// Razorpay
// ------------------------------------------------------------------
function apf_razorpay_request($method, $path, $body = null) {
    $keyId = apf_setting('razorpay_key_id');
    $secret = apf_setting('razorpay_key_secret');
    if (!$keyId || !$secret) return [0, ['error' => ['description' => 'Razorpay is not configured']]];
    $base = defined('APF_RAZORPAY_API') ? APF_RAZORPAY_API : 'https://api.razorpay.com/v1';
    $ch = curl_init($base . $path);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 20, CURLOPT_CUSTOMREQUEST => $method,
        CURLOPT_USERPWD => $keyId . ':' . $secret,
        CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
    ]);
    if ($body !== null) curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($body));
    $resp = curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    if (PHP_VERSION_ID < 80000) curl_close($ch);
    return [$code, json_decode((string)$resp, true) ?: []];
}
