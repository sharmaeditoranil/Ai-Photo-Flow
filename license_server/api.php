<?php
/**
 * Ai PhotoFlow License Server - public JSON API used by the desktop app.
 * All prices, coupons, payments and licenses are decided here, never in the app.
 */
define('APF_SERVER', 1);
require_once __DIR__ . '/lib/core.php';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');

function out($data, $code = 200) {
    http_response_code($code);
    echo json_encode($data, JSON_UNESCAPED_SLASHES);
    exit;
}
function fail($error, $code = 'ERROR', $http = 400) { out(['ok' => false, 'error' => $error, 'code' => $code], $http); }

if (!apf_is_https() && !apf_is_local()) fail('HTTPS required', 'HTTPS', 403);

$route = isset($_GET['r']) ? preg_replace('/[^a-z_]/', '', $_GET['r']) : '';
$raw = file_get_contents('php://input');
$in = json_decode($raw ?: '{}', true);
if (!is_array($in)) $in = [];
$ip = apf_ip();

// General per-IP limit for every API call
if ($route !== 'webhook' && !apf_rate_limit('api:' . $ip, 120, 60)) fail('Too many requests. Please wait a minute.', 'RATE_LIMIT', 429);

function need_machine($in) {
    $m = apf_clean_machine($in['machine_id'] ?? '');
    if (strlen($m) < 8) fail('Missing machine id', 'BAD_REQUEST');
    return $m;
}

try {
switch ($route) {

case 'ping':
    out(['ok' => true, 'server' => 'Ai PhotoFlow License Server', 'time' => time()]);

case 'plans':
    out(['ok' => true, 'prices' => apf_prices(), 'devices' => apf_devices(),
         'trial_days' => (int)apf_setting('trial_days'),
         'payments_enabled' => apf_setting('payments_enabled') === '1' && apf_setting('razorpay_key_id') !== '',
         'razorpay_key_id' => apf_setting('razorpay_key_id')]);

case 'trial': {
    $mid = need_machine($in);
    if (!apf_rate_limit('trial:' . $ip, 20, 3600)) fail('Too many requests', 'RATE_LIMIT', 429);
    $db = apf_db();
    $st = $db->prepare('SELECT * FROM trials WHERE machine_id = ?');
    $st->execute([$mid]);
    $t = $st->fetch();
    $now = time();
    if (!$t) {
        $days = max(0, (int)apf_setting('trial_days'));
        $db->prepare('INSERT INTO trials (machine_id, started_at, expires_at, last_seen, os, machine_name, last_ip) VALUES (?, ?, ?, ?, ?, ?, ?)')
           ->execute([$mid, $now, $now + $days * 86400, $now, apf_str($in['os'] ?? '', 60), apf_str($in['machine_name'] ?? '', 80), $ip]);
        $st->execute([$mid]);
        $t = $st->fetch();
        apf_audit('app', 'trial_start', ['machine' => $mid]);
    } else {
        $db->prepare('UPDATE trials SET last_seen = ?, last_ip = ? WHERE machine_id = ?')->execute([$now, $ip, $mid]);
    }
    if ((int)$t['blocked']) fail('Free trial is not available on this computer.', 'TRIAL_BLOCKED', 403);
    if ((int)$t['expires_at'] <= $now) fail('Your free trial has ended. Please buy a plan to continue.', 'TRIAL_EXPIRED', 403);
    out(['ok' => true, 'token' => apf_trial_token($t), 'expires_at' => (int)$t['expires_at']]);
}

case 'activate':
case 'refresh': {
    $mid = need_machine($in);
    $key = apf_clean_key($in['license_key'] ?? '');
    // Brute-force guard: only WRONG keys count, so customers sharing an IP (mobile CGNAT) are never
    // locked out with a correct key. Keys are 100-bit random, guessing is hopeless anyway.
    $lic = $key ? apf_get_license_by_key($key) : null;
    if (!$lic) {
        if (!apf_rate_limit('badkey:' . $ip, 20, 3600)) fail('Too many invalid license keys. Try again in an hour.', 'RATE_LIMIT', 429);
        fail('Invalid license key. Please check and try again.', 'INVALID_KEY', 404);
    }
    $state = apf_license_state($lic);
    if ($state !== 'ACTIVE') {
        $msg = $state === 'EXPIRED' ? 'This license has expired. Please renew your plan.'
             : 'This license has been ' . strtolower($state) . '. Please contact support.';
        fail($msg, $state, 403);
    }
    if ($route === 'refresh') {
        $st = apf_db()->prepare('SELECT active FROM activations WHERE license_id = ? AND machine_id = ?');
        $st->execute([$lic['id'], $mid]);
        if ((int)$st->fetchColumn() !== 1) fail('This computer was removed from the license. Please activate again.', 'DEACTIVATED', 403);
    }
    list($ok, $code, $msg) = apf_activate_machine($lic, $mid, $in['machine_name'] ?? '', $in['os'] ?? '', $in['app_version'] ?? '');
    if (!$ok) fail($msg, $code, 403);
    out(['ok' => true, 'token' => apf_license_token($lic, $mid), 'license' => apf_public_license($lic)]);
}

case 'deactivate': {
    $mid = need_machine($in);
    $lic = apf_get_license_by_key($in['license_key'] ?? '');
    if (!$lic) fail('Invalid license key', 'INVALID_KEY', 404);
    // Only the computer holding a valid token for this key can release itself
    $tok = apf_verify_token($in['token'] ?? '');
    if (!$tok || ($tok['lic'] ?? '') !== $lic['license_key'] || ($tok['mid'] ?? '') !== $mid) fail('Not authorised', 'FORBIDDEN', 403);
    apf_db()->prepare('UPDATE activations SET active = 0 WHERE license_id = ? AND machine_id = ?')->execute([$lic['id'], $mid]);
    apf_audit('app', 'deactivate', ['license' => $lic['license_key'], 'machine' => $mid]);
    out(['ok' => true]);
}

case 'profile': {
    // Customer's own plan details. Proof of ownership = a server-signed token for this key + computer.
    $mid = need_machine($in);
    $lic = apf_get_license_by_key($in['license_key'] ?? '');
    $tok = apf_verify_token($in['token'] ?? '');
    if (!$lic || !$tok || ($tok['lic'] ?? '') !== $lic['license_key'] || ($tok['mid'] ?? '') !== $mid) fail('Not authorised', 'FORBIDDEN', 403);
    $db = apf_db();
    $st = $db->prepare('SELECT machine_id, machine_name, os, first_seen, last_seen FROM activations WHERE license_id = ? AND active = 1 ORDER BY first_seen');
    $st->execute([$lic['id']]);
    $devices = [];
    foreach ($st->fetchAll() as $a) {
        $devices[] = ['name' => $a['machine_name'] ?: 'Computer', 'os' => $a['os'], 'first_seen' => (int)$a['first_seen'],
                      'last_seen' => (int)$a['last_seen'], 'this_computer' => $a['machine_id'] === $mid];
    }
    $st = $db->prepare("SELECT order_id, plan, cycle, currency, amount, base_amount, coupon, payment_id, paid_at
                        FROM orders WHERE license_id = ? AND status = 'PAID' ORDER BY paid_at DESC");
    $st->execute([$lic['id']]);
    $orders = [];
    foreach ($st->fetchAll() as $o) {
        $orders[] = ['date' => (int)$o['paid_at'], 'plan' => $o['plan'], 'cycle' => $o['cycle'], 'currency' => $o['currency'],
                     'amount' => (float)$o['amount'], 'original_amount' => (float)$o['base_amount'], 'coupon' => $o['coupon'],
                     'payment_id' => $o['payment_id']];
    }
    out(['ok' => true, 'license' => apf_public_license($lic), 'devices' => $devices, 'orders' => $orders]);
}

case 'quote': {
    $q = apf_quote(strtoupper($in['plan'] ?? ''), strtolower($in['cycle'] ?? ''), strtoupper($in['currency'] ?? 'INR'), $in['coupon'] ?? '');
    if (!$q['ok']) fail($q['error'], 'COUPON');
    unset($q['agent_id']);
    out($q);
}

case 'order': {
    $mid = need_machine($in);
    if (!apf_rate_limit('order:' . $ip, 15, 600)) fail('Too many payment attempts. Please wait a few minutes.', 'RATE_LIMIT', 429);
    $plan = strtoupper($in['plan'] ?? '');
    if (!in_array($plan, ['PRO', 'STUDIO'], true)) fail('Invalid plan');
    $currency = strtoupper($in['currency'] ?? 'INR') === 'USD' ? 'USD' : 'INR';
    $q = apf_quote($plan, strtolower($in['cycle'] ?? ''), $currency, $in['coupon'] ?? '');
    if (!$q['ok']) fail($q['error'], 'COUPON');
    $name = apf_str($in['name'] ?? '', 100);
    $email = apf_str($in['email'] ?? '', 120);
    $phone = apf_str($in['phone'] ?? '', 30);
    if ($name === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) fail('Please enter your name and a valid email address.');
    if (strlen(preg_replace('/\D/', '', $phone)) < 10) fail('Please enter a valid mobile number.');

    $db = apf_db();
    $insert = $db->prepare('INSERT INTO orders (order_id, plan, cycle, currency, base_amount, amount, coupon, agent_id,
        customer_name, customer_email, customer_phone, machine_id, status, created_at, last_ip)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, \'CREATED\', ?, ?)');

    if ($q['final_price'] <= 0) {
        // 100% coupon: no payment needed, licence issued directly (coupon usage limits still apply)
        $orderId = 'free_' . bin2hex(random_bytes(8));
        $insert->execute([$orderId, $plan, $q['cycle'], $currency, $q['original_price'], 0, $q['coupon'], $q['agent_id'],
                          $name, $email, $phone, $mid, time(), $ip]);
        $lic = apf_fulfill_order($orderId, 'FREE_COUPON', 'app');
        list($ok, $code, $msg) = apf_activate_machine($lic, $mid, $in['machine_name'] ?? '', $in['os'] ?? '', $in['app_version'] ?? '');
        if (!$ok) fail($msg, $code, 403);
        out(['ok' => true, 'free' => true, 'token' => apf_license_token($lic, $mid), 'license' => apf_public_license($lic)]);
    }

    if (apf_setting('payments_enabled') !== '1' || apf_setting('razorpay_key_id') === '') {
        fail('Online payment is not available right now. Please contact support.', 'PAYMENTS_OFF', 503);
    }
    $units = (int)round($q['final_price'] * 100);
    list($code, $rp) = apf_razorpay_request('POST', '/orders', [
        'amount' => $units, 'currency' => $currency, 'receipt' => 'apf_' . bin2hex(random_bytes(6)),
        'payment_capture' => 1,
        'notes' => ['plan' => $plan, 'cycle' => $q['cycle'], 'email' => $email, 'coupon' => $q['coupon']],
    ]);
    if ($code !== 200 || empty($rp['id'])) {
        $desc = $rp['error']['description'] ?? 'Payment gateway error';
        apf_audit('app', 'order_failed', ['http' => $code, 'error' => $desc]);
        fail('Could not start payment: ' . $desc, 'GATEWAY', 502);
    }
    $insert->execute([$rp['id'], $plan, $q['cycle'], $currency, $q['original_price'], $q['final_price'], $q['coupon'],
                      $q['agent_id'], $name, $email, $phone, $mid, time(), $ip]);
    out(['ok' => true, 'free' => false, 'order_id' => $rp['id'], 'key_id' => apf_setting('razorpay_key_id'),
         'amount' => $units, 'currency' => $currency, 'description' => $plan . ' plan (' . $q['cycle'] . ')',
         'name' => apf_setting('business_name')]);
}

case 'verify': {
    $mid = need_machine($in);
    $orderId = apf_str($in['order_id'] ?? '', 80);
    $paymentId = apf_str($in['payment_id'] ?? '', 80);
    $signature = apf_str($in['signature'] ?? '', 200);
    $secret = apf_setting('razorpay_key_secret');
    if (!$orderId || !$paymentId || !$signature || !$secret) fail('Payment details missing');
    $expected = hash_hmac('sha256', $orderId . '|' . $paymentId, $secret);
    if (!hash_equals($expected, $signature)) {
        apf_audit('app', 'verify_bad_signature', ['order' => $orderId, 'payment' => $paymentId]);
        fail('Payment verification failed.', 'BAD_SIGNATURE', 403);
    }
    $lic = apf_fulfill_order($orderId, $paymentId, 'app');
    if (!$lic) fail('Order not found', 'NOT_FOUND', 404);
    list($ok, $code, $msg) = apf_activate_machine($lic, $mid, $in['machine_name'] ?? '', $in['os'] ?? '', $in['app_version'] ?? '');
    if (!$ok) fail($msg, $code, 403);
    out(['ok' => true, 'token' => apf_license_token($lic, $mid), 'license' => apf_public_license($lic)]);
}

case 'order_status': {
    // Recovers a payment completed while the app was closed (licence created by the webhook)
    $mid = need_machine($in);
    $st = apf_db()->prepare('SELECT * FROM orders WHERE order_id = ?');
    $st->execute([apf_str($in['order_id'] ?? '', 80)]);
    $o = $st->fetch();
    if (!$o || $o['machine_id'] !== $mid) fail('Order not found', 'NOT_FOUND', 404);
    if ($o['status'] !== 'PAID' || !$o['license_id']) out(['ok' => true, 'paid' => false]);
    $st = apf_db()->prepare('SELECT * FROM licenses WHERE id = ?');
    $st->execute([$o['license_id']]);
    $lic = $st->fetch();
    list($ok, $code, $msg) = apf_activate_machine($lic, $mid, $in['machine_name'] ?? '', $in['os'] ?? '', $in['app_version'] ?? '');
    if (!$ok) fail($msg, $code, 403);
    out(['ok' => true, 'paid' => true, 'token' => apf_license_token($lic, $mid), 'license' => apf_public_license($lic)]);
}

case 'webhook': {
    // Razorpay -> server. Configure in Razorpay Dashboard: event "order.paid", URL .../api.php?r=webhook
    $secret = apf_setting('razorpay_webhook_secret');
    $sig = $_SERVER['HTTP_X_RAZORPAY_SIGNATURE'] ?? '';
    if (!$secret || !$sig || !hash_equals(hash_hmac('sha256', $raw, $secret), $sig)) {
        apf_audit('razorpay', 'webhook_bad_signature', '');
        fail('Bad signature', 'FORBIDDEN', 403);
    }
    $event = $in['event'] ?? '';
    $payment = $in['payload']['payment']['entity'] ?? [];
    $orderId = $payment['order_id'] ?? ($in['payload']['order']['entity']['id'] ?? '');
    if (in_array($event, ['order.paid', 'payment.captured'], true) && $orderId) {
        $st = apf_db()->prepare('SELECT amount, currency FROM orders WHERE order_id = ?');
        $st->execute([$orderId]);
        $o = $st->fetch();
        $paid = isset($payment['amount']) ? (int)$payment['amount'] : null;
        if ($o && ($paid === null || $paid >= (int)round($o['amount'] * 100))) {
            apf_fulfill_order($orderId, $payment['id'] ?? 'WEBHOOK', 'razorpay');
        }
    }
    out(['ok' => true]);
}

default:
    fail('Unknown endpoint', 'NOT_FOUND', 404);
}
} catch (Throwable $e) {
    error_log('APF license API: ' . $e->getMessage());
    fail('Server error. Please try again.', 'SERVER', 500);
}
