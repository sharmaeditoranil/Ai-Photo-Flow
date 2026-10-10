<?php
/**
 * Ai PhotoFlow License Server - owner admin panel.
 * Licenses, devices, payments, coupons, partners, commissions, trials, gateway settings and security.
 */
define('APF_SERVER', 1);
require_once __DIR__ . '/lib/core.php';
require_once __DIR__ . '/lib/auth.php';

apf_require_https();
header('X-Frame-Options: DENY');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
header('Cache-Control: no-store, private');
$CSP_NONCE = base64_encode(random_bytes(12));
header("Content-Security-Policy: default-src 'self'; script-src 'self' 'nonce-$CSP_NONCE' https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline'; img-src 'self' data:; form-action 'self'; frame-ancestors 'none'; base-uri 'none'");
if (apf_is_https()) header('Strict-Transport-Security: max-age=31536000');

$db = apf_db();
$page = isset($_GET['p']) ? preg_replace('/[^a-z_]/', '', $_GET['p']) : 'dashboard';
$isPost = $_SERVER['REQUEST_METHOD'] === 'POST';

function flash($msg, $type = 'ok') { apf_session_start(); $_SESSION['apf_flash'][] = [$type, $msg]; }
function go($p, $extra = '') { header('Location: admin.php?p=' . $p . $extra); exit; }
function post($k, $d = '') { return isset($_POST[$k]) ? (is_string($_POST[$k]) ? trim($_POST[$k]) : $_POST[$k]) : $d; }
function sel($a, $b) { return (string)$a === (string)$b ? ' selected' : ''; }

// ======================================================================
// Layout
// ======================================================================
function layout_start($title, $admin = null) {
    global $page;
    apf_session_start();
    $flashes = $_SESSION['apf_flash'] ?? [];
    unset($_SESSION['apf_flash']);
    $nav = ['dashboard' => '📊 Dashboard', 'licenses' => '👤 Users & Licenses', 'orders' => '💳 Payments', 'coupons' => '🏷️ Coupons',
            'partners' => '🤝 Partners', 'commissions' => '💰 Commissions', 'trials' => '⏳ Trials',
            'settings' => '⚙️ Gateway & Prices', 'security' => '🛡️ Security'];
    ?><!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow"><title><?= h($title) ?> · Ai PhotoFlow Admin</title>
<style>
:root{--bg:#0b0e14;--card:#121722;--line:#222b3d;--text:#e6ebf3;--mut:#8b97ab;--pri:#3b82f6;--ok:#10b981;--warn:#f59e0b;--bad:#ef4444}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
a{color:#60a5fa;text-decoration:none}a:hover{text-decoration:underline}
.wrap{display:flex;min-height:100vh}.side{width:230px;background:#0e121b;border-right:1px solid var(--line);padding:18px 12px;flex-shrink:0}
.side h1{font-size:15px;margin:0 8px 18px}.side a{display:block;padding:9px 10px;border-radius:8px;color:var(--text);margin-bottom:2px}
.side a.on,.side a:hover{background:#1a2233;text-decoration:none}.main{flex:1;padding:24px 28px;min-width:0}
h2{margin:0 0 16px;font-size:20px}h3{font-size:15px;margin:22px 0 10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:16px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}.stat b{display:block;font-size:22px;margin-top:4px}
.stat span{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mut);font-weight:600;font-size:11px;text-transform:uppercase}.tw{overflow-x:auto}
input,select,textarea{background:#0a0d14;border:1px solid #2a354d;color:var(--text);border-radius:8px;padding:8px 10px;font:inherit;width:100%}
label{display:block;font-size:12px;color:var(--mut);margin:0 0 4px}.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:12px}
button,.btn{background:var(--pri);color:#fff;border:0;border-radius:8px;padding:8px 14px;font:inherit;font-weight:600;cursor:pointer;display:inline-block}
.btn2{background:#1f2738;color:var(--text);border:1px solid #2d3850}.bad{background:var(--bad)}.okb{background:var(--ok)}.sm{padding:4px 10px;font-size:12px}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700}
.b-ok{background:rgba(16,185,129,.15);color:#34d399}.b-bad{background:rgba(239,68,68,.15);color:#f87171}.b-warn{background:rgba(245,158,11,.15);color:#fbbf24}.b-mut{background:#1f2738;color:var(--mut)}
.flash{padding:10px 14px;border-radius:8px;margin-bottom:14px}.flash.ok{background:rgba(16,185,129,.12);border:1px solid rgba(16,185,129,.35)}
.flash.err{background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.35)}.mut{color:var(--mut)}.mono{font-family:ui-monospace,Menlo,monospace}
.inline{display:inline}.actions form{display:inline-block;margin:2px 4px 2px 0}.narrow{max-width:420px;margin:60px auto}
@media(max-width:800px){.wrap{display:block}.side{width:auto;display:flex;flex-wrap:wrap;gap:4px}.side h1{width:100%}.main{padding:16px}}
</style></head><body>
<?php if ($admin): ?>
<div class="wrap"><nav class="side"><h1>🔐 Ai PhotoFlow Admin</h1>
<?php foreach ($nav as $k => $v): ?><a href="admin.php?p=<?= $k ?>" class="<?= $page === $k ? 'on' : '' ?>"><?= $v ?></a><?php endforeach; ?>
<form method="post" action="admin.php?p=logout" style="margin-top:14px"><?= apf_csrf_field() ?><button class="btn2" style="width:100%">Logout (<?= h($admin['username']) ?>)</button></form>
</nav><main class="main">
<?php else: ?><main class="narrow"><?php endif; ?>
<?php foreach ($flashes as $f): ?><div class="flash <?= $f[0] === 'ok' ? 'ok' : 'err' ?>"><?= h($f[1]) ?></div><?php endforeach;
}

function layout_end($admin = null) {
    echo $admin ? '</main></div></body></html>' : '</main></body></html>';
}

function status_badge($s) {
    $map = ['ACTIVE' => 'b-ok', 'PAID' => 'b-ok', 'EXPIRED' => 'b-warn', 'PENDING' => 'b-warn', 'CREATED' => 'b-mut',
            'SUSPENDED' => 'b-warn', 'REVOKED' => 'b-bad', 'INACTIVE' => 'b-mut', 'BLOCKED' => 'b-bad'];
    return '<span class="badge ' . ($map[$s] ?? 'b-mut') . '">' . h($s) . '</span>';
}

function agents_list() { return apf_db()->query("SELECT id, name, status FROM agents ORDER BY name")->fetchAll(); }

// ======================================================================
// First-time setup (only possible while no admin exists, and only with the setup code)
// ======================================================================
$adminCount = (int)$db->query('SELECT COUNT(*) FROM admins')->fetchColumn();
if ($adminCount === 0) {
    apf_session_start();
    if ($isPost) {
        apf_csrf_check();
        if (!apf_rate_limit('setup:' . apf_ip(), 10, 3600)) { flash('Too many attempts. Try again later.', 'err'); go('setup'); }
        $step = post('step');
        if ($step === '1') {
            $u = post('username'); $pw = post('password');
            if (!hash_equals(APF_SETUP_CODE, strtoupper(post('setup_code')))) { flash('Wrong setup code.', 'err'); go('setup'); }
            if (!preg_match('/^[A-Za-z0-9_.@-]{4,40}$/', $u)) { flash('Username: 4-40 letters/numbers.', 'err'); go('setup'); }
            if ($e = apf_password_problem($pw)) { flash($e, 'err'); go('setup'); }
            if ($pw !== post('password2')) { flash('Passwords do not match.', 'err'); go('setup'); }
            $_SESSION['setup'] = ['u' => $u, 'h' => password_hash($pw, PASSWORD_DEFAULT), 't' => apf_base32_encode(random_bytes(20))];
            go('setup');
        } elseif ($step === '2' && !empty($_SESSION['setup'])) {
            $s = $_SESSION['setup'];
            $stepNo = apf_totp_verify($s['t'], post('code'));
            if (!$stepNo) { flash('Code is wrong. Check the time on your phone and try again.', 'err'); go('setup'); }
            list($plain, $hashes) = apf_new_recovery_codes();
            $db->prepare('INSERT INTO admins (username, pass_hash, totp_secret, totp_last_step, recovery_codes, created_at) VALUES (?, ?, ?, ?, ?, ?)')
               ->execute([$s['u'], $s['h'], $s['t'], $stepNo, $hashes, time()]);
            unset($_SESSION['setup']);
            apf_audit($s['u'], 'admin_created', '');
            $_SESSION['show_recovery'] = $plain;
            go('login');
        }
        go('setup');
    }
    layout_start('Setup');
    $s = $_SESSION['setup'] ?? null; ?>
    <div class="card"><h2>🔐 First-time setup</h2>
    <?php if (!$s): ?>
      <p class="mut">Create the owner account. You need the <b>setup code</b> from the installation guide.</p>
      <form method="post"><?= apf_csrf_field() ?><input type="hidden" name="step" value="1">
      <p><label>Setup code</label><input name="setup_code" required autocomplete="off"></p>
      <p><label>Username</label><input name="username" required autocomplete="username"></p>
      <p><label>Password (12+ chars, upper, lower, number, symbol)</label><input type="password" name="password" required autocomplete="new-password"></p>
      <p><label>Repeat password</label><input type="password" name="password2" required autocomplete="new-password"></p>
      <button>Continue</button></form>
    <?php else: $uri = 'otpauth://totp/' . rawurlencode('Ai PhotoFlow Admin:' . $s['u']) . '?secret=' . $s['t'] . '&issuer=' . rawurlencode('Ai PhotoFlow'); ?>
      <p>Step 2: open <b>Google Authenticator</b> (or Microsoft Authenticator) on your phone → <b>+</b> → scan this QR code.</p>
      <div id="qr" style="background:#fff;padding:12px;display:inline-block;border-radius:8px"></div>
      <p class="mut">Can't scan? Enter this key manually: <span class="mono"><?= h(trim(chunk_split($s['t'], 4, ' '))) ?></span></p>
      <form method="post"><?= apf_csrf_field() ?><input type="hidden" name="step" value="2">
      <p><label>6-digit code shown in the app</label><input name="code" inputmode="numeric" maxlength="6" required autocomplete="one-time-code"></p>
      <button>Finish setup</button></form>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js" nonce="<?= h($GLOBALS['CSP_NONCE']) ?>"></script>
      <script nonce="<?= h($GLOBALS['CSP_NONCE']) ?>">new QRCode(document.getElementById('qr'), {text: <?= json_encode($uri) ?>, width: 200, height: 200});</script>
    <?php endif; ?></div>
    <?php layout_end();
    exit;
}

// ======================================================================
// Login
// ======================================================================
if ($page === 'logout' && $isPost) { apf_csrf_check(); $a = apf_admin(); if ($a) apf_audit($a['username'], 'logout', ''); apf_logout(); go('login'); }

$admin = apf_admin();
if (!$admin) {
    apf_session_start();
    if ($isPost && $page === 'login') {
        apf_csrf_check();
        if (apf_login_locked()) { flash('Too many failed logins. Login is locked for a while — try again later.', 'err'); go('login'); }
        $st = $db->prepare('SELECT * FROM admins WHERE username = ?');
        $st->execute([post('username')]);
        $a = $st->fetch();
        $okPw = $a && password_verify(post('password'), $a['pass_hash']);
        $stepNo = 0; $usedRecovery = false;
        if ($okPw) {
            $code = post('code');
            $stepNo = apf_totp_verify($a['totp_secret'], $code, (int)$a['totp_last_step']);
            if (!$stepNo && strlen($code) > 6) $usedRecovery = apf_use_recovery_code($a, $code);
        }
        if (!$okPw || (!$stepNo && !$usedRecovery)) { apf_login_failed(post('username')); flash('Wrong username, password or code.', 'err'); go('login'); }
        if ($stepNo) $db->prepare('UPDATE admins SET totp_last_step = ? WHERE id = ?')->execute([$stepNo, $a['id']]);
        if (password_needs_rehash($a['pass_hash'], PASSWORD_DEFAULT)) {
            $db->prepare('UPDATE admins SET pass_hash = ? WHERE id = ?')->execute([password_hash(post('password'), PASSWORD_DEFAULT), $a['id']]);
        }
        $db->prepare('UPDATE admins SET last_login_at = ?, last_login_ip = ? WHERE id = ?')->execute([time(), apf_ip(), $a['id']]);
        $showRecovery = $_SESSION['show_recovery'] ?? null;
        apf_login_session($a);
        if ($showRecovery) $_SESSION['show_recovery'] = $showRecovery;
        apf_audit($a['username'], $usedRecovery ? 'login_recovery_code' : 'login', '');
        if ($usedRecovery) flash('You logged in with a recovery code. It cannot be used again. Generate new codes in Security if few remain.', 'err');
        go('dashboard');
    }
    layout_start('Login'); ?>
    <div class="card"><h2>🔐 Ai PhotoFlow Admin</h2>
    <?php if (!empty($_SESSION['show_recovery'])): ?><div class="flash ok">Setup complete! Now log in with your password and the 6-digit code.</div><?php endif; ?>
    <form method="post" action="admin.php?p=login"><?= apf_csrf_field() ?>
    <p><label>Username</label><input name="username" required autocomplete="username" autofocus></p>
    <p><label>Password</label><input type="password" name="password" required autocomplete="current-password"></p>
    <p><label>6-digit code from Authenticator app (or a recovery code)</label><input name="code" required autocomplete="one-time-code"></p>
    <button style="width:100%">Login</button></form></div>
    <?php layout_end();
    exit;
}

$who = $admin['username'];

// ======================================================================
// POST actions (all require CSRF token)
// ======================================================================
if ($isPost) {
    apf_csrf_check();
    $a = post('action');
    try {
    switch ($a) {
    // ---------- Licenses ----------
    case 'license_create':
        $plan = post('plan');
        $lic = apf_create_license([
            'plan' => $plan, 'cycle' => post('cycle'), 'days' => post('days') !== '' ? (int)post('days') : null,
            'max_devices' => (int)post('max_devices'), 'customer_name' => post('customer_name'),
            'customer_email' => post('customer_email'), 'customer_phone' => post('customer_phone'),
            'source' => 'MANUAL', 'agent_id' => post('agent_id') ? (int)post('agent_id') : null, 'notes' => post('notes'),
        ]);
        apf_audit($who, 'license_create', ['key' => $lic['license_key'], 'plan' => $lic['plan']]);
        flash('License created: ' . $lic['license_key']);
        go('license', '&id=' . $lic['id']);
    case 'license_status':
        $s = post('status');
        if (!in_array($s, ['ACTIVE', 'SUSPENDED', 'REVOKED'], true)) break;
        $db->prepare('UPDATE licenses SET status = ? WHERE id = ?')->execute([$s, (int)post('id')]);
        apf_audit($who, 'license_status', ['id' => (int)post('id'), 'status' => $s]);
        flash('License status changed to ' . $s . '. Computers will be updated on their next online check (within 24 h).');
        go('license', '&id=' . (int)post('id'));
    case 'license_extend':
        $id = (int)post('id'); $days = (int)post('days');
        $st = $db->prepare('SELECT expires_at FROM licenses WHERE id = ?'); $st->execute([$id]); $exp = $st->fetchColumn();
        if ($days > 0 && $exp) {
            $newExp = max((int)$exp, time()) + $days * 86400;
            $db->prepare('UPDATE licenses SET expires_at = ? WHERE id = ?')->execute([$newExp, $id]);
            apf_audit($who, 'license_extend', ['id' => $id, 'days' => $days]);
            flash('Extended by ' . $days . ' days.');
        }
        go('license', '&id=' . $id);
    case 'license_edit':
        $id = (int)post('id');
        $db->prepare('UPDATE licenses SET customer_name = ?, customer_email = ?, customer_phone = ?, max_devices = ?, notes = ? WHERE id = ?')
           ->execute([apf_str(post('customer_name')), apf_str(post('customer_email')), apf_str(post('customer_phone'), 40),
                      max(1, (int)post('max_devices')), apf_str(post('notes'), 1000), $id]);
        apf_audit($who, 'license_edit', ['id' => $id]);
        flash('Saved.');
        go('license', '&id=' . $id);
    case 'device_remove':
        $db->prepare('UPDATE activations SET active = 0 WHERE id = ? AND license_id = ?')->execute([(int)post('act_id'), (int)post('id')]);
        apf_audit($who, 'device_remove', ['license' => (int)post('id'), 'activation' => (int)post('act_id')]);
        flash('Computer removed. The seat is free for a new computer.');
        go('license', '&id=' . (int)post('id'));

    // ---------- Orders ----------
    case 'offline_sale':
        $plan = post('plan'); $cycle = post('cycle');
        // No partner picked: the customer's referring partner (first purchase) still earns the commission
        $agentId = post('agent_id') ? (int)post('agent_id')
                                    : apf_referral_agent('', post('customer_email'), post('customer_phone'));
        $orderId = 'offline_' . bin2hex(random_bytes(6));
        $db->prepare('INSERT INTO orders (order_id, plan, cycle, currency, base_amount, amount, coupon, agent_id, customer_name,
            customer_email, customer_phone, status, created_at, last_ip) VALUES (?, ?, ?, ?, ?, ?, \'\', ?, ?, ?, ?, \'CREATED\', ?, ?)')
           ->execute([$orderId, in_array($plan, APF_PLANS, true) ? $plan : 'PRO', array_key_exists($cycle, APF_CYCLES) ? $cycle : 'yearly',
                      post('currency') === 'USD' ? 'USD' : 'INR', (float)post('amount'), (float)post('amount'), $agentId,
                      apf_str(post('customer_name')), apf_str(post('customer_email')), apf_str(post('customer_phone'), 40), time(), apf_ip()]);
        $lic = apf_fulfill_order($orderId, apf_str(post('payment_ref'), 80) ?: 'OFFLINE', $who);
        flash('Offline sale recorded. License: ' . $lic['license_key']);
        go('license', '&id=' . $lic['id']);

    // ---------- Coupons ----------
    case 'coupon_save':
        $code = strtoupper(preg_replace('/[^A-Za-z0-9_\-]/', '', post('code')));
        $pct = (float)post('discount_percent');
        if ($code === '' || strlen($code) > 30 || $pct <= 0 || $pct > 100) { flash('Code (max 30 chars) and discount 1-100% required.', 'err'); go('coupons'); }
        $plans = array_values(array_intersect((array)($_POST['plans'] ?? []), ['PRO', 'STUDIO']));
        $until = post('valid_until') ? strtotime(post('valid_until') . ' 23:59:59') : null;
        $db->prepare('INSERT INTO coupons (code, discount_percent, max_uses, valid_until, plans, agent_id, active, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(code) DO UPDATE SET discount_percent = excluded.discount_percent,
            max_uses = excluded.max_uses, valid_until = excluded.valid_until, plans = excluded.plans, agent_id = excluded.agent_id,
            active = excluded.active, notes = excluded.notes')
           ->execute([$code, $pct, max(0, (int)post('max_uses')), $until, implode(',', $plans),
                      post('agent_id') ? (int)post('agent_id') : null, post('active') ? 1 : 0, apf_str(post('notes'), 300), time()]);
        apf_audit($who, 'coupon_save', ['code' => $code, 'pct' => $pct, 'max_uses' => (int)post('max_uses')]);
        flash('Coupon ' . $code . ' saved.' . ($pct >= 100 && (int)post('max_uses') === 0 ? ' WARNING: 100% coupon with unlimited uses gives free licenses to anyone who knows it!' : ''),
              $pct >= 100 && (int)post('max_uses') === 0 ? 'err' : 'ok');
        go('coupons');
    case 'coupon_toggle':
        $db->prepare('UPDATE coupons SET active = 1 - active WHERE code = ?')->execute([post('code')]);
        apf_audit($who, 'coupon_toggle', ['code' => post('code')]);
        go('coupons');
    case 'coupon_delete':
        $st = $db->prepare('SELECT used_count FROM coupons WHERE code = ?'); $st->execute([post('code')]);
        if ((int)$st->fetchColumn() > 0) { flash('Coupon already used — disable it instead of deleting (keeps sales history).', 'err'); go('coupons'); }
        $db->prepare('DELETE FROM coupons WHERE code = ?')->execute([post('code')]);
        apf_audit($who, 'coupon_delete', ['code' => post('code')]);
        go('coupons');

    // ---------- Partners ----------
    case 'partner_save':
        $id = (int)post('id');
        $vals = [apf_str(post('name'), 100), apf_str(post('phone'), 30), apf_str(post('email'), 120),
                 min(100, max(0, (float)post('commission_percent'))), apf_str(post('payout_upi'), 100), apf_str(post('payout_bank'), 300),
                 post('status') === 'INACTIVE' ? 'INACTIVE' : 'ACTIVE', apf_str(post('notes'), 500)];
        if ($vals[0] === '') { flash('Partner name is required.', 'err'); go('partners'); }
        if ($id) {
            $db->prepare('UPDATE agents SET name=?, phone=?, email=?, commission_percent=?, payout_upi=?, payout_bank=?, status=?, notes=? WHERE id=?')
               ->execute(array_merge($vals, [$id]));
        } else {
            $db->prepare('INSERT INTO agents (name, phone, email, commission_percent, payout_upi, payout_bank, status, notes, created_at) VALUES (?,?,?,?,?,?,?,?,?)')
               ->execute(array_merge($vals, [time()]));
            $id = (int)$db->lastInsertId();
            if (post('coupon_code')) {
                $code = strtoupper(preg_replace('/[^A-Za-z0-9_\-]/', '', post('coupon_code')));
                $db->prepare('INSERT OR IGNORE INTO coupons (code, discount_percent, max_uses, plans, agent_id, active, notes, created_at) VALUES (?, ?, 0, \'\', ?, 1, ?, ?)')
                   ->execute([$code, min(100, max(1, (float)post('coupon_discount') ?: 10)), $id, 'Referral code for ' . $vals[0], time()]);
            }
        }
        apf_audit($who, 'partner_save', ['id' => $id, 'name' => $vals[0]]);
        flash('Partner saved.');
        go('partners');

    // ---------- Commissions ----------
    case 'commission_pay':
        $ref = apf_str(post('payout_ref'), 100);
        if ($ref === '') { flash('Enter the UPI / bank reference number.', 'err'); go('commissions'); }
        $db->prepare("UPDATE commissions SET status = 'PAID', payout_ref = ?, paid_at = ? WHERE id = ? AND status = 'PENDING'")
           ->execute([$ref, time(), (int)post('id')]);
        apf_audit($who, 'commission_paid', ['id' => (int)post('id'), 'ref' => $ref]);
        flash('Commission marked as paid.');
        go('commissions');

    // ---------- Trials ----------
    case 'trial_block':
        $db->prepare('UPDATE trials SET blocked = 1 - blocked WHERE machine_id = ?')->execute([post('machine_id')]);
        apf_audit($who, 'trial_block_toggle', ['machine' => post('machine_id')]);
        go('trials');
    case 'trial_extend':
        $days = max(1, min(365, (int)post('days')));
        $db->prepare('UPDATE trials SET expires_at = MAX(expires_at, ?) + ? WHERE machine_id = ?')->execute([time(), $days * 86400, post('machine_id')]);
        apf_audit($who, 'trial_extend', ['machine' => post('machine_id'), 'days' => $days]);
        flash('Trial extended by ' . $days . ' days.');
        go('trials');

    // ---------- Settings ----------
    case 'settings_gateway':
        apf_set_setting('razorpay_key_id', preg_replace('/[^A-Za-z0-9_]/', '', post('razorpay_key_id')));
        if (post('razorpay_key_secret') !== '') apf_set_setting('razorpay_key_secret', post('razorpay_key_secret'));
        if (post('razorpay_webhook_secret') !== '') apf_set_setting('razorpay_webhook_secret', post('razorpay_webhook_secret'));
        apf_set_setting('payments_enabled', post('payments_enabled') ? '1' : '0');
        apf_set_setting('business_name', apf_str(post('business_name'), 80) ?: 'Ai PhotoFlow');
        apf_audit($who, 'settings_gateway', ['key_id' => post('razorpay_key_id'), 'secret_changed' => post('razorpay_key_secret') !== '']);
        flash('Payment gateway settings saved.');
        go('settings');
    case 'settings_test':
        list($code, $rp) = apf_razorpay_request('GET', '/orders?count=1');
        flash($code === 200 ? '✅ Razorpay connection works (' . (strpos(apf_setting('razorpay_key_id'), 'rzp_live_') === 0 ? 'LIVE' : 'TEST') . ' mode).'
                            : '❌ Razorpay error: ' . ($rp['error']['description'] ?? 'HTTP ' . $code), $code === 200 ? 'ok' : 'err');
        go('settings');
    case 'settings_prices':
        $prices = [];
        foreach (['INR', 'USD'] as $c) foreach (['PRO', 'STUDIO'] as $pl) foreach (['monthly', 'yearly'] as $cy) {
            $v = (float)($_POST['price'][$c][$pl][$cy] ?? 0);
            if ($v <= 0) { flash("Price for $pl $cy ($c) must be more than 0.", 'err'); go('settings'); }
            $prices[$c][$pl][$cy] = $v;
        }
        $devices = [];
        foreach (APF_PLANS as $pl) $devices[$pl] = max(1, min(50, (int)($_POST['devices'][$pl] ?? 1)));
        apf_set_setting('prices', json_encode($prices));
        apf_set_setting('devices', json_encode($devices));
        apf_set_setting('trial_days', (string)max(0, min(90, (int)post('trial_days'))));
        apf_set_setting('offline_grace_days', (string)max(1, min(90, (int)post('offline_grace_days'))));
        apf_audit($who, 'settings_prices', ['prices' => $prices, 'devices' => $devices]);
        flash('Prices and plan settings saved. The app shows the new prices immediately.');
        go('settings');

    // ---------- Security ----------
    case 'sec_password':
        if (!password_verify(post('current'), $admin['pass_hash']) || !apf_totp_verify($admin['totp_secret'], post('code'), (int)$admin['totp_last_step'])) {
            apf_audit($who, 'password_change_failed', ''); flash('Current password or code is wrong.', 'err'); go('security');
        }
        if ($e = apf_password_problem(post('new'))) { flash($e, 'err'); go('security'); }
        if (post('new') !== post('new2')) { flash('New passwords do not match.', 'err'); go('security'); }
        $db->prepare('UPDATE admins SET pass_hash = ?, totp_last_step = ? WHERE id = ?')
           ->execute([password_hash(post('new'), PASSWORD_DEFAULT), (int)floor(time() / 30) + 1, $admin['id']]);
        apf_audit($who, 'password_changed', '');
        apf_login_session($admin);
        flash('Password changed.');
        go('security');
    case 'sec_recovery':
        if (!apf_totp_verify($admin['totp_secret'], post('code'), (int)$admin['totp_last_step'])) { flash('Code is wrong.', 'err'); go('security'); }
        list($plain, $hashes) = apf_new_recovery_codes();
        $db->prepare('UPDATE admins SET recovery_codes = ?, totp_last_step = ? WHERE id = ?')->execute([$hashes, (int)floor(time() / 30) + 1, $admin['id']]);
        apf_audit($who, 'recovery_codes_regenerated', '');
        $_SESSION['show_recovery'] = $plain;
        go('security');
    case 'sec_totp_reset':
        if (!password_verify(post('current'), $admin['pass_hash']) || !apf_totp_verify($admin['totp_secret'], post('code'), (int)$admin['totp_last_step'])) {
            flash('Password or code is wrong.', 'err'); go('security');
        }
        $_SESSION['new_totp'] = apf_base32_encode(random_bytes(20));
        go('security');
    case 'sec_totp_confirm':
        $new = $_SESSION['new_totp'] ?? '';
        $stepNo = $new ? apf_totp_verify($new, post('code')) : 0;
        if (!$stepNo) { flash('Code from the NEW entry is wrong.', 'err'); go('security'); }
        $db->prepare('UPDATE admins SET totp_secret = ?, totp_last_step = ? WHERE id = ?')->execute([$new, $stepNo, $admin['id']]);
        unset($_SESSION['new_totp']);
        apf_audit($who, 'totp_changed', '');
        flash('Authenticator changed. Delete the old entry from your phone.');
        go('security');
    }
    } catch (Throwable $e) {
        error_log('APF admin: ' . $e->getMessage());
        flash('Error: ' . $e->getMessage(), 'err');
    }
    go($page);
}

// ======================================================================
// Pages
// ======================================================================
layout_start(ucfirst($page), $admin);

if (!empty($_SESSION['show_recovery'])): $codes = $_SESSION['show_recovery']; unset($_SESSION['show_recovery']); ?>
  <div class="card" style="border-color:var(--warn)"><h3 style="margin-top:0">⚠️ Save your recovery codes NOW</h3>
  <p>If you lose your phone, each code lets you log in <b>once</b>. They are shown only this one time. Write them down / keep them safe offline.</p>
  <p class="mono" style="font-size:16px;line-height:2"><?= implode('<br>', array_map('h', $codes)) ?></p></div>
<?php endif;

switch ($page) {

case 'dashboard':
    $now = time();
    $rev = $db->query("SELECT currency, SUM(amount) s, COUNT(*) n FROM orders WHERE status='PAID' GROUP BY currency")->fetchAll();
    $rev30 = $db->query("SELECT currency, SUM(amount) s FROM orders WHERE status='PAID' AND paid_at > " . ($now - 30 * 86400) . " GROUP BY currency")->fetchAll();
    $activeLic = (int)$db->query("SELECT COUNT(*) FROM licenses WHERE status='ACTIVE' AND (expires_at IS NULL OR expires_at > $now)")->fetchColumn();
    $devices = (int)$db->query("SELECT COUNT(*) FROM activations a JOIN licenses l ON l.id=a.license_id WHERE a.active=1 AND l.status='ACTIVE'")->fetchColumn();
    $seen7 = (int)$db->query("SELECT COUNT(*) FROM activations WHERE active=1 AND last_seen > " . ($now - 7 * 86400))->fetchColumn();
    $trials = (int)$db->query("SELECT COUNT(*) FROM trials WHERE expires_at > $now AND blocked=0")->fetchColumn();
    $pend = (float)$db->query("SELECT COALESCE(SUM(amount),0) FROM commissions WHERE status='PENDING'")->fetchColumn();
    $exp30 = (int)$db->query("SELECT COUNT(*) FROM licenses WHERE status='ACTIVE' AND expires_at BETWEEN $now AND " . ($now + 30 * 86400))->fetchColumn();
    $fmt = function ($rows) { if (!$rows) return '₹0'; return implode(' + ', array_map(function ($r) { return apf_money($r['s'], $r['currency']); }, $rows)); };
    ?>
    <h2>Dashboard</h2>
    <?php if (apf_setting('razorpay_key_id') === ''): ?><div class="flash err">Payment gateway is not set up yet. Go to <a href="admin.php?p=settings">Gateway &amp; Prices</a>.</div><?php endif; ?>
    <div class="grid">
      <div class="stat"><span>Total revenue</span><b><?= h($fmt($rev)) ?></b><span class="mut"><?= array_sum(array_column($rev, 'n')) ?> paid orders</span></div>
      <div class="stat"><span>Last 30 days</span><b><?= h($fmt($rev30)) ?></b></div>
      <div class="stat"><span>Active licenses</span><b><?= $activeLic ?></b><span class="mut"><?= $exp30 ?> expire in 30 days</span></div>
      <div class="stat"><span>Active computers</span><b><?= $devices ?></b><span class="mut"><?= $seen7 ?> online in last 7 days</span></div>
      <div class="stat"><span>Running trials</span><b><?= $trials ?></b></div>
      <div class="stat"><span>Commission to pay</span><b><?= h(apf_money($pend)) ?></b></div>
    </div>
    <div class="card"><h3 style="margin-top:0">Latest payments</h3><div class="tw"><table><tr><th>Date</th><th>Customer</th><th>Plan</th><th>Amount</th><th>Coupon</th><th>Status</th></tr>
    <?php foreach ($db->query("SELECT * FROM orders ORDER BY id DESC LIMIT 10") as $o): ?>
      <tr><td><?= apf_date($o['created_at']) ?></td><td><?= h($o['customer_name']) ?><br><span class="mut"><?= h($o['customer_email']) ?></span></td>
      <td><?= h($o['plan'] . ' / ' . $o['cycle']) ?></td><td><?= h(apf_money($o['amount'], $o['currency'])) ?></td><td><?= h($o['coupon']) ?></td><td><?= status_badge($o['status']) ?></td></tr>
    <?php endforeach; ?></table></div></div>
    <?php break;

case 'licenses':
    $q = trim($_GET['q'] ?? '');
    $sql = 'SELECT l.*, (SELECT COUNT(*) FROM activations a WHERE a.license_id = l.id AND a.active = 1) AS devs FROM licenses l';
    $args = [];
    if ($q !== '') { $sql .= ' WHERE l.license_key LIKE ? OR l.customer_email LIKE ? OR l.customer_name LIKE ? OR l.customer_phone LIKE ?'; $args = array_fill(0, 4, '%' . $q . '%'); }
    $st = $db->prepare($sql . ' ORDER BY l.id DESC LIMIT 300'); $st->execute($args); ?>
    <h2>Users &amp; Licenses</h2>
    <div class="card"><h3 style="margin-top:0">➕ Create license manually</h3>
    <form method="post"><?= apf_csrf_field() ?><input type="hidden" name="action" value="license_create">
    <div class="row"><div><label>Plan</label><select name="plan"><option>PRO</option><option>STUDIO</option><option value="VIP_LIFETIME">VIP_LIFETIME (free, lifetime)</option></select></div>
    <div><label>Duration</label><select name="cycle"><option value="yearly">1 year</option><option value="monthly">1 month</option><option value="lifetime">Lifetime</option></select></div>
    <div><label>Or custom days</label><input name="days" type="number" min="1" placeholder="e.g. 90"></div>
    <div><label>Max computers (blank = plan default)</label><input name="max_devices" type="number" min="1"></div></div>
    <div class="row"><div><label>Customer name</label><input name="customer_name" required></div><div><label>Email</label><input name="customer_email" type="email"></div>
    <div><label>Phone</label><input name="customer_phone"></div><div><label>Partner (optional)</label><select name="agent_id"><option value="">—</option>
    <?php foreach (agents_list() as $ag): ?><option value="<?= $ag['id'] ?>"><?= h($ag['name']) ?></option><?php endforeach; ?></select></div></div>
    <p><label>Notes</label><input name="notes"></p><button>Create license</button></form></div>
    <div class="card"><form method="get" class="row"><input type="hidden" name="p" value="licenses"><div><input name="q" value="<?= h($q) ?>" placeholder="Search key, name, email, phone"></div><div><button class="btn2">Search</button></div></form>
    <div class="tw"><table><tr><th>User</th><th>Mobile</th><th>Key</th><th>Plan</th><th>Activated</th><th>Expires</th><th>Days left</th><th>Computers</th><th>Status</th><th>Source</th></tr>
    <?php foreach ($st as $l): $left = $l['expires_at'] ? max(0, (int)floor(((int)$l['expires_at'] - time()) / 86400)) : null; ?><tr>
      <td><a href="admin.php?p=license&id=<?= $l['id'] ?>"><?= h($l['customer_name'] ?: '—') ?></a><br><span class="mut"><?= h($l['customer_email']) ?></span></td>
      <td><?= h($l['customer_phone'] ?: '—') ?></td>
      <td class="mono"><a href="admin.php?p=license&id=<?= $l['id'] ?>"><?= h($l['license_key']) ?></a></td><td><?= h($l['plan']) ?></td>
      <td><?= apf_date($l['created_at']) ?></td>
      <td><?= $l['expires_at'] ? apf_date($l['expires_at']) : 'Lifetime' ?></td><td><?= $left === null ? '∞' : $left ?></td><td><?= (int)$l['devs'] ?> / <?= (int)$l['max_devices'] ?></td>
      <td><?= status_badge(apf_license_state($l)) ?></td><td class="mut"><?= h($l['source']) ?></td></tr><?php endforeach; ?></table></div></div>
    <?php break;

case 'license':
    $st = $db->prepare('SELECT * FROM licenses WHERE id = ?'); $st->execute([(int)($_GET['id'] ?? 0)]); $l = $st->fetch();
    if (!$l) { echo '<p>Not found.</p>'; break; }
    $acts = $db->prepare('SELECT * FROM activations WHERE license_id = ? ORDER BY active DESC, last_seen DESC'); $acts->execute([$l['id']]); ?>
    <h2>License <span class="mono"><?= h($l['license_key']) ?></span> <?= status_badge(apf_license_state($l)) ?></h2>
    <div class="card"><div class="row">
      <div><label>Plan</label><?= h($l['plan']) ?> (<?= h($l['cycle']) ?>)</div><div><label>Expires</label><?= $l['expires_at'] ? apf_date($l['expires_at']) : 'Lifetime' ?></div>
      <div><label>Created</label><?= apf_date($l['created_at']) ?> · <?= h($l['source']) ?></div><div><label>Order</label><span class="mono"><?= h($l['order_id'] ?: '—') ?></span></div></div>
    <div class="actions">
      <?php foreach (['ACTIVE' => 'okb', 'SUSPENDED' => 'btn2', 'REVOKED' => 'bad'] as $s => $cls): if ($l['status'] === $s) continue; ?>
        <form method="post"><?= apf_csrf_field() ?><input type="hidden" name="action" value="license_status"><input type="hidden" name="id" value="<?= $l['id'] ?>">
        <input type="hidden" name="status" value="<?= $s ?>"><button class="<?= $cls ?> sm"><?= $s === 'ACTIVE' ? 'Re-activate' : ($s === 'SUSPENDED' ? 'Suspend' : 'Revoke (block)') ?></button></form>
      <?php endforeach; if ($l['expires_at']): ?>
        <form method="post"><?= apf_csrf_field() ?><input type="hidden" name="action" value="license_extend"><input type="hidden" name="id" value="<?= $l['id'] ?>">
        <input name="days" type="number" min="1" value="365" style="width:90px"> <button class="btn2 sm">Extend days</button></form>
      <?php endif; ?></div></div>
    <div class="card"><h3 style="margin-top:0">Customer</h3><form method="post"><?= apf_csrf_field() ?><input type="hidden" name="action" value="license_edit"><input type="hidden" name="id" value="<?= $l['id'] ?>">
    <div class="row"><div><label>Name</label><input name="customer_name" value="<?= h($l['customer_name']) ?>"></div><div><label>Email</label><input name="customer_email" value="<?= h($l['customer_email']) ?>"></div>
    <div><label>Phone</label><input name="customer_phone" value="<?= h($l['customer_phone']) ?>"></div><div><label>Max computers</label><input name="max_devices" type="number" min="1" value="<?= (int)$l['max_devices'] ?>"></div></div>
    <p><label>Notes</label><input name="notes" value="<?= h($l['notes']) ?>"></p><button class="btn2">Save</button></form></div>
    <?php $ords = $db->prepare("SELECT * FROM orders WHERE license_id = ? ORDER BY id DESC"); $ords->execute([$l['id']]); $ords = $ords->fetchAll(); ?>
    <div class="card"><h3 style="margin-top:0">Payments</h3><?php if (!$ords): ?><p class="mut">No payment linked (manual / free license).</p><?php else: ?>
    <div class="tw"><table><tr><th>Date</th><th>Order / Payment</th><th>Plan</th><th>Amount</th><th>Coupon</th><th>Status</th></tr>
    <?php foreach ($ords as $o): ?><tr><td><?= apf_date($o['paid_at'] ?: $o['created_at']) ?></td><td class="mono"><?= h($o['order_id']) ?><br><span class="mut"><?= h($o['payment_id']) ?></span></td>
      <td><?= h($o['plan'] . ' / ' . $o['cycle']) ?></td><td><?= h(apf_money($o['amount'], $o['currency'])) ?></td><td><?= h($o['coupon']) ?></td><td><?= status_badge($o['status']) ?></td></tr><?php endforeach; ?>
    </table></div><?php endif; ?></div>
    <div class="card"><h3 style="margin-top:0">Computers</h3><div class="tw"><table><tr><th>Computer</th><th>Machine ID</th><th>First seen</th><th>Last online</th><th>IP</th><th></th></tr>
    <?php foreach ($acts as $a): ?><tr><td><?= h($a['machine_name'] ?: '—') ?><br><span class="mut"><?= h($a['os']) ?> <?= h($a['app_version']) ?></span></td><td class="mono"><?= h($a['machine_id']) ?></td>
      <td><?= apf_date($a['first_seen']) ?></td><td><?= apf_date($a['last_seen']) ?></td><td class="mut"><?= h($a['last_ip']) ?></td>
      <td><?php if ((int)$a['active']): ?><form method="post"><?= apf_csrf_field() ?><input type="hidden" name="action" value="device_remove"><input type="hidden" name="id" value="<?= $l['id'] ?>">
      <input type="hidden" name="act_id" value="<?= $a['id'] ?>"><button class="btn2 sm">Remove</button></form><?php else: ?><span class="badge b-mut">removed</span><?php endif; ?></td></tr>
    <?php endforeach; ?></table></div></div>
    <?php break;

case 'orders':
    $f = $_GET['status'] ?? '';
    $st = $f ? $db->prepare('SELECT * FROM orders WHERE status = ? ORDER BY id DESC LIMIT 300') : $db->prepare('SELECT * FROM orders ORDER BY id DESC LIMIT 300');
    $st->execute($f ? [$f] : []); ?>
    <h2>Payments</h2>
    <div class="card"><h3 style="margin-top:0">➕ Record offline / cash / bank sale</h3>
    <form method="post"><?= apf_csrf_field() ?><input type="hidden" name="action" value="offline_sale">
    <div class="row"><div><label>Plan</label><select name="plan"><option>PRO</option><option>STUDIO</option></select></div>
    <div><label>Duration</label><select name="cycle"><option value="yearly">1 year</option><option value="monthly">1 month</option></select></div>
    <div><label>Amount received</label><input name="amount" type="number" step="0.01" min="0" required></div>
    <div><label>Currency</label><select name="currency"><option>INR</option><option>USD</option></select></div></div>
    <div class="row"><div><label>Customer name</label><input name="customer_name" required></div><div><label>Email</label><input name="customer_email" type="email"></div>
    <div><label>Phone</label><input name="customer_phone"></div><div><label>Payment reference</label><input name="payment_ref" placeholder="UPI / bank ref"></div>
    <div><label>Partner (commission)</label><select name="agent_id"><option value="">—</option><?php foreach (agents_list() as $ag): ?><option value="<?= $ag['id'] ?>"><?= h($ag['name']) ?></option><?php endforeach; ?></select></div></div>
    <button>Record sale &amp; create license</button></form></div>
    <div class="card"><p><?php foreach (['' => 'All', 'PAID' => 'Paid', 'CREATED' => 'Started (not paid)'] as $k => $v): ?><a class="btn2 btn sm" href="admin.php?p=orders&status=<?= $k ?>"><?= $v ?></a> <?php endforeach; ?></p>
    <div class="tw"><table><tr><th>Date</th><th>Order / Payment</th><th>Customer</th><th>Plan</th><th>Amount</th><th>Coupon</th><th>Status</th><th>License</th></tr>
    <?php foreach ($st as $o): ?><tr><td><?= apf_date($o['created_at']) ?></td><td class="mono"><?= h($o['order_id']) ?><br><span class="mut"><?= h($o['payment_id']) ?></span></td>
      <td><?= h($o['customer_name']) ?><br><span class="mut"><?= h($o['customer_email']) ?> <?= h($o['customer_phone']) ?></span></td><td><?= h($o['plan'] . ' / ' . $o['cycle']) ?></td>
      <td><?= h(apf_money($o['amount'], $o['currency'])) ?><?php if ($o['amount'] != $o['base_amount']): ?><br><span class="mut">was <?= h(apf_money($o['base_amount'], $o['currency'])) ?></span><?php endif; ?></td>
      <td><?= h($o['coupon']) ?></td><td><?= status_badge($o['status']) ?></td><td><?= $o['license_id'] ? '<a href="admin.php?p=license&id=' . (int)$o['license_id'] . '">open</a>' : '' ?></td></tr>
    <?php endforeach; ?></table></div></div>
    <?php break;

case 'coupons':
    $edit = null;
    if (!empty($_GET['code'])) { $st = $db->prepare('SELECT * FROM coupons WHERE code = ?'); $st->execute([$_GET['code']]); $edit = $st->fetch(); }
    $e = $edit ?: ['code' => '', 'discount_percent' => 10, 'max_uses' => 0, 'valid_until' => null, 'plans' => '', 'agent_id' => null, 'active' => 1, 'notes' => ''];
    $ePlans = $e['plans'] === '' ? [] : explode(',', $e['plans']); ?>
    <h2>Coupons</h2>
    <div class="card"><h3 style="margin-top:0"><?= $edit ? 'Edit coupon ' . h($e['code']) : '➕ New coupon' ?></h3>
    <form method="post"><?= apf_csrf_field() ?><input type="hidden" name="action" value="coupon_save">
    <div class="row"><div><label>Code</label><input name="code" value="<?= h($e['code']) ?>" <?= $edit ? 'readonly' : '' ?> required maxlength="30" style="text-transform:uppercase"></div>
    <div><label>Discount %</label><input name="discount_percent" type="number" step="0.01" min="1" max="100" value="<?= h($e['discount_percent']) ?>" required></div>
    <div><label>Max uses (0 = unlimited)</label><input name="max_uses" type="number" min="0" value="<?= (int)$e['max_uses'] ?>"></div>
    <div><label>Valid until (blank = no end)</label><input name="valid_until" type="date" value="<?= $e['valid_until'] ? date('Y-m-d', (int)$e['valid_until']) : '' ?>"></div></div>
    <div class="row"><div><label>Plans (none ticked = all)</label><label style="display:inline"><input type="checkbox" name="plans[]" value="PRO" style="width:auto" <?= in_array('PRO', $ePlans) ? 'checked' : '' ?>> PRO</label>
      &nbsp; <label style="display:inline"><input type="checkbox" name="plans[]" value="STUDIO" style="width:auto" <?= in_array('STUDIO', $ePlans) ? 'checked' : '' ?>> STUDIO</label></div>
    <div><label>Partner (gets commission)</label><select name="agent_id"><option value="">—</option><?php foreach (agents_list() as $ag): ?><option value="<?= $ag['id'] ?>"<?= sel($ag['id'], $e['agent_id']) ?>><?= h($ag['name']) ?></option><?php endforeach; ?></select></div>
    <div><label>Status</label><label style="display:inline"><input type="checkbox" name="active" value="1" style="width:auto" <?= (int)$e['active'] ? 'checked' : '' ?>> Active</label></div>
    <div><label>Notes</label><input name="notes" value="<?= h($e['notes']) ?>"></div></div>
    <button>Save coupon</button> <?php if ($edit): ?><a href="admin.php?p=coupons">Cancel</a><?php endif; ?></form></div>
    <div class="card"><div class="tw"><table><tr><th>Code</th><th>Discount</th><th>Used</th><th>Valid until</th><th>Plans</th><th>Partner</th><th>Status</th><th></th></tr>
    <?php foreach ($db->query('SELECT c.*, a.name AS agent FROM coupons c LEFT JOIN agents a ON a.id = c.agent_id ORDER BY c.created_at DESC') as $c): ?>
      <tr><td class="mono"><?= h($c['code']) ?></td><td><?= (float)$c['discount_percent'] ?>%</td><td><?= (int)$c['used_count'] ?><?= (int)$c['max_uses'] ? ' / ' . (int)$c['max_uses'] : '' ?></td>
      <td><?= $c['valid_until'] ? date('d M Y', (int)$c['valid_until']) : '—' ?></td><td><?= h($c['plans'] ?: 'All') ?></td><td><?= h($c['agent'] ?: '—') ?></td>
      <td><?= status_badge((int)$c['active'] ? 'ACTIVE' : 'INACTIVE') ?></td><td class="actions"><a class="btn btn2 sm" href="admin.php?p=coupons&code=<?= urlencode($c['code']) ?>">Edit</a>
      <form method="post"><?= apf_csrf_field() ?><input type="hidden" name="action" value="coupon_toggle"><input type="hidden" name="code" value="<?= h($c['code']) ?>"><button class="btn2 sm"><?= (int)$c['active'] ? 'Disable' : 'Enable' ?></button></form>
      <?php if (!(int)$c['used_count']): ?><form method="post"><?= apf_csrf_field() ?><input type="hidden" name="action" value="coupon_delete"><input type="hidden" name="code" value="<?= h($c['code']) ?>"><button class="bad sm">Delete</button></form><?php endif; ?></td></tr>
    <?php endforeach; ?></table></div></div>
    <?php break;

case 'partners':
    $edit = null;
    if (!empty($_GET['id'])) { $st = $db->prepare('SELECT * FROM agents WHERE id = ?'); $st->execute([(int)$_GET['id']]); $edit = $st->fetch(); }
    $e = $edit ?: ['id' => 0, 'name' => '', 'phone' => '', 'email' => '', 'commission_percent' => 20, 'payout_upi' => '', 'payout_bank' => '', 'status' => 'ACTIVE', 'notes' => '']; ?>
    <h2>Partners (referral agents)</h2>
    <div class="card"><h3 style="margin-top:0"><?= $edit ? 'Edit partner' : '➕ New partner' ?></h3>
    <form method="post"><?= apf_csrf_field() ?><input type="hidden" name="action" value="partner_save"><input type="hidden" name="id" value="<?= (int)$e['id'] ?>">
    <div class="row"><div><label>Name</label><input name="name" value="<?= h($e['name']) ?>" required></div><div><label>Phone</label><input name="phone" value="<?= h($e['phone']) ?>"></div>
    <div><label>Email</label><input name="email" value="<?= h($e['email']) ?>"></div><div><label>Commission %</label><input name="commission_percent" type="number" step="0.01" min="0" max="100" value="<?= h($e['commission_percent']) ?>"></div></div>
    <div class="row"><div><label>UPI ID</label><input name="payout_upi" value="<?= h($e['payout_upi']) ?>"></div><div><label>Bank details</label><input name="payout_bank" value="<?= h($e['payout_bank']) ?>"></div>
    <div><label>Status</label><select name="status"><option<?= sel('ACTIVE', $e['status']) ?>>ACTIVE</option><option<?= sel('INACTIVE', $e['status']) ?>>INACTIVE</option></select></div>
    <div><label>Notes</label><input name="notes" value="<?= h($e['notes']) ?>"></div></div>
    <?php if (!$edit): ?><div class="row"><div><label>Referral coupon code (optional)</label><input name="coupon_code" placeholder="e.g. RAJESH10" style="text-transform:uppercase"></div>
      <div><label>Customer discount % for that code</label><input name="coupon_discount" type="number" min="1" max="100" value="10"></div></div><?php endif; ?>
    <button>Save partner</button> <?php if ($edit): ?><a href="admin.php?p=partners">Cancel</a><?php endif; ?></form></div>
    <div class="card"><div class="tw"><table><tr><th>Partner</th><th>Codes</th><th>Sales</th><th>Commission %</th><th>Pending</th><th>Paid</th><th>Status</th><th></th></tr>
    <?php foreach ($db->query("SELECT a.*, (SELECT GROUP_CONCAT(code, ', ') FROM coupons WHERE agent_id = a.id) codes,
        (SELECT COUNT(*) FROM orders WHERE agent_id = a.id AND status='PAID') sales, (SELECT COALESCE(SUM(amount),0) FROM orders WHERE agent_id = a.id AND status='PAID') revenue,
        (SELECT COALESCE(SUM(amount),0) FROM commissions WHERE agent_id = a.id AND status='PENDING') pend,
        (SELECT COALESCE(SUM(amount),0) FROM commissions WHERE agent_id = a.id AND status='PAID') paid FROM agents a ORDER BY a.name") as $a): ?>
      <tr><td><?= h($a['name']) ?><br><span class="mut"><?= h($a['phone']) ?> <?= h($a['payout_upi']) ?></span></td><td class="mono"><?= h($a['codes'] ?: '—') ?></td>
      <td><?= (int)$a['sales'] ?> · <?= h(apf_money($a['revenue'])) ?></td><td><?= (float)$a['commission_percent'] ?>%</td><td><?= h(apf_money($a['pend'])) ?></td><td><?= h(apf_money($a['paid'])) ?></td>
      <td><?= status_badge($a['status']) ?></td><td><a class="btn btn2 sm" href="admin.php?p=partners&id=<?= $a['id'] ?>">Edit</a></td></tr>
    <?php endforeach; ?></table></div></div>
    <?php break;

case 'commissions': ?>
    <h2>Commissions</h2>
    <div class="card"><div class="tw"><table><tr><th>Date</th><th>Partner</th><th>Payout to</th><th>Sale</th><th>Commission</th><th>Status</th><th></th></tr>
    <?php foreach ($db->query("SELECT c.*, a.name, a.payout_upi, a.payout_bank FROM commissions c JOIN agents a ON a.id = c.agent_id ORDER BY c.status = 'PAID', c.id DESC LIMIT 300") as $c): ?>
      <tr><td><?= apf_date($c['created_at']) ?></td><td><?= h($c['name']) ?></td><td class="mut"><?= h($c['payout_upi']) ?><br><?= h($c['payout_bank']) ?></td>
      <td><?= h(apf_money($c['sale_amount'])) ?><br><span class="mono mut"><?= h($c['order_id']) ?></span></td><td><b><?= h(apf_money($c['amount'])) ?></b> (<?= (float)$c['rate'] ?>%)</td>
      <td><?= status_badge($c['status']) ?><?php if ($c['status'] === 'PAID'): ?><br><span class="mut"><?= h($c['payout_ref']) ?> · <?= apf_date($c['paid_at']) ?></span><?php endif; ?></td>
      <td><?php if ($c['status'] === 'PENDING'): ?><form method="post" class="actions"><?= apf_csrf_field() ?><input type="hidden" name="action" value="commission_pay"><input type="hidden" name="id" value="<?= $c['id'] ?>">
        <input name="payout_ref" placeholder="UPI/bank ref" required style="width:140px"> <button class="okb sm">Mark paid</button></form><?php endif; ?></td></tr>
    <?php endforeach; ?></table></div></div>
    <?php break;

case 'trials': ?>
    <h2>Free trials</h2><p class="mut">One free trial per computer. Reinstalling the app does not give a new trial.</p>
    <div class="card"><div class="tw"><table><tr><th>Computer</th><th>Machine ID</th><th>Started</th><th>Ends</th><th>Last online</th><th>Status</th><th></th></tr>
    <?php foreach ($db->query('SELECT * FROM trials ORDER BY started_at DESC LIMIT 300') as $t): $st = (int)$t['blocked'] ? 'BLOCKED' : ((int)$t['expires_at'] > time() ? 'ACTIVE' : 'EXPIRED'); ?>
      <tr><td><?= h($t['machine_name'] ?: '—') ?><br><span class="mut"><?= h($t['os']) ?> · <?= h($t['last_ip']) ?></span></td><td class="mono"><?= h($t['machine_id']) ?></td>
      <td><?= apf_date($t['started_at']) ?></td><td><?= apf_date($t['expires_at']) ?></td><td><?= apf_date($t['last_seen']) ?></td><td><?= status_badge($st) ?></td>
      <td class="actions"><form method="post"><?= apf_csrf_field() ?><input type="hidden" name="action" value="trial_extend"><input type="hidden" name="machine_id" value="<?= h($t['machine_id']) ?>">
        <input name="days" type="number" min="1" max="365" value="7" style="width:70px"> <button class="btn2 sm">Extend</button></form>
        <form method="post"><?= apf_csrf_field() ?><input type="hidden" name="action" value="trial_block"><input type="hidden" name="machine_id" value="<?= h($t['machine_id']) ?>"><button class="<?= (int)$t['blocked'] ? 'okb' : 'bad' ?> sm"><?= (int)$t['blocked'] ? 'Unblock' : 'Block' ?></button></form></td></tr>
    <?php endforeach; ?></table></div></div>
    <?php break;

case 'settings':
    $prices = apf_prices(); $devs = apf_devices();
    $base = (apf_is_https() ? 'https://' : 'http://') . $_SERVER['HTTP_HOST'] . rtrim(dirname($_SERVER['SCRIPT_NAME']), '/');
    $secretSet = apf_setting('razorpay_key_secret') !== ''; $whSet = apf_setting('razorpay_webhook_secret') !== ''; ?>
    <h2>Gateway &amp; Prices</h2>
    <div class="card"><h3 style="margin-top:0">💳 Razorpay payment gateway</h3>
    <p class="mut">Keys are stored only on this server. The desktop app never sees the secret. Get keys in Razorpay Dashboard → Account &amp; Settings → API Keys.</p>
    <form method="post"><?= apf_csrf_field() ?><input type="hidden" name="action" value="settings_gateway">
    <div class="row"><div><label>Key ID (rzp_live_… or rzp_test_…)</label><input name="razorpay_key_id" value="<?= h(apf_setting('razorpay_key_id')) ?>" autocomplete="off"></div>
    <div><label>Key Secret <?= $secretSet ? '(saved — leave blank to keep)' : '' ?></label><input type="password" name="razorpay_key_secret" autocomplete="new-password"></div>
    <div><label>Webhook Secret <?= $whSet ? '(saved — leave blank to keep)' : '' ?></label><input type="password" name="razorpay_webhook_secret" autocomplete="new-password"></div>
    <div><label>Business name on checkout</label><input name="business_name" value="<?= h(apf_setting('business_name')) ?>"></div></div>
    <p><label style="display:inline"><input type="checkbox" name="payments_enabled" value="1" style="width:auto" <?= apf_setting('payments_enabled') === '1' ? 'checked' : '' ?>> Accept online payments</label></p>
    <button>Save gateway</button></form>
    <form method="post" style="margin-top:10px"><?= apf_csrf_field() ?><input type="hidden" name="action" value="settings_test"><button class="btn2">Test Razorpay connection</button></form>
    <p class="mut" style="margin-top:12px">Webhook (Razorpay Dashboard → Webhooks → Add): URL <span class="mono"><?= h($base) ?>/api.php?r=webhook</span>, event <b>order.paid</b>, same secret as above. It activates licenses even if the customer closes the app during payment.</p></div>
    <div class="card"><h3 style="margin-top:0">💰 Prices &amp; plans</h3>
    <form method="post"><?= apf_csrf_field() ?><input type="hidden" name="action" value="settings_prices">
    <div class="tw"><table><tr><th>Currency</th><th>PRO monthly</th><th>PRO yearly</th><th>STUDIO monthly</th><th>STUDIO yearly</th></tr>
    <?php foreach (['INR', 'USD'] as $c): ?><tr><td><?= $c ?></td><?php foreach (['PRO', 'STUDIO'] as $pl) foreach (['monthly', 'yearly'] as $cy): ?>
      <td><input name="price[<?= $c ?>][<?= $pl ?>][<?= $cy ?>]" type="number" step="0.01" min="1" value="<?= h($prices[$c][$pl][$cy] ?? '') ?>"></td><?php endforeach; ?></tr><?php endforeach; ?></table></div>
    <div class="row" style="margin-top:12px"><?php foreach (APF_PLANS as $pl): ?><div><label>Computers per <?= $pl ?> license</label><input name="devices[<?= $pl ?>]" type="number" min="1" max="50" value="<?= (int)($devs[$pl] ?? 1) ?>"></div><?php endforeach; ?>
    <div><label>Free trial days</label><input name="trial_days" type="number" min="0" max="90" value="<?= (int)apf_setting('trial_days') ?>"></div>
    <div><label>Days the app may work offline</label><input name="offline_grace_days" type="number" min="1" max="90" value="<?= (int)apf_setting('offline_grace_days') ?>"></div></div>
    <button>Save prices &amp; plans</button></form></div>
    <?php break;

case 'security': ?>
    <h2>Security</h2>
    <div class="card"><p>Logged in as <b><?= h($admin['username']) ?></b>. Last login: <?= apf_date($admin['last_login_at']) ?> from <?= h($admin['last_login_ip']) ?>.
    Recovery codes left: <b><?= count(json_decode($admin['recovery_codes'] ?: '[]', true) ?: []) ?></b>.</p>
    <p class="mut">Private data folder: <span class="mono"><?= h(apf_data_dir()) ?></span></p></div>
    <div class="card"><h3 style="margin-top:0">Change password</h3><form method="post"><?= apf_csrf_field() ?><input type="hidden" name="action" value="sec_password">
    <div class="row"><div><label>Current password</label><input type="password" name="current" required></div><div><label>New password</label><input type="password" name="new" required autocomplete="new-password"></div>
    <div><label>Repeat new password</label><input type="password" name="new2" required autocomplete="new-password"></div><div><label>Authenticator code</label><input name="code" required inputmode="numeric"></div></div>
    <button>Change password</button></form></div>
    <div class="card"><h3 style="margin-top:0">Recovery codes</h3><form method="post" class="row"><?= apf_csrf_field() ?><input type="hidden" name="action" value="sec_recovery">
    <div><label>Authenticator code</label><input name="code" required inputmode="numeric"></div><div><label>&nbsp;</label><button class="btn2">Generate new codes (old ones stop working)</button></div></form></div>
    <div class="card"><h3 style="margin-top:0">Move Authenticator to a new phone</h3>
    <?php if (!empty($_SESSION['new_totp'])): $nt = $_SESSION['new_totp']; $uri = 'otpauth://totp/' . rawurlencode('Ai PhotoFlow Admin:' . $admin['username']) . '?secret=' . $nt . '&issuer=' . rawurlencode('Ai PhotoFlow'); ?>
      <div id="qr" style="background:#fff;padding:12px;display:inline-block;border-radius:8px"></div><p class="mono"><?= h(trim(chunk_split($nt, 4, ' '))) ?></p>
      <form method="post" class="row"><?= apf_csrf_field() ?><input type="hidden" name="action" value="sec_totp_confirm"><div><label>Code from the NEW entry</label><input name="code" required></div><div><label>&nbsp;</label><button>Confirm</button></div></form>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js" nonce="<?= h($CSP_NONCE) ?>"></script>
      <script nonce="<?= h($CSP_NONCE) ?>">new QRCode(document.getElementById('qr'), {text: <?= json_encode($uri) ?>, width: 200, height: 200});</script>
    <?php else: ?>
      <form method="post" class="row"><?= apf_csrf_field() ?><input type="hidden" name="action" value="sec_totp_reset"><div><label>Current password</label><input type="password" name="current" required></div>
      <div><label>Current code</label><input name="code" required></div><div><label>&nbsp;</label><button class="btn2">Start</button></div></form>
    <?php endif; ?></div>
    <div class="card"><h3 style="margin-top:0">Activity log (last 200)</h3><div class="tw"><table><tr><th>Time</th><th>Who</th><th>Action</th><th>Details</th><th>IP</th></tr>
    <?php foreach ($db->query('SELECT * FROM audit_log ORDER BY id DESC LIMIT 200') as $r): ?><tr><td><?= apf_date($r['ts']) ?></td><td><?= h($r['actor']) ?></td>
      <td><?= h($r['action']) ?></td><td class="mono mut" style="max-width:380px;word-break:break-all"><?= h(mb_substr($r['details'], 0, 300)) ?></td><td class="mut"><?= h($r['ip']) ?></td></tr><?php endforeach; ?></table></div></div>
    <?php break;

default:
    echo '<p>Page not found.</p>';
}

layout_end($admin);
