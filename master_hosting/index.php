<?php
/**
 * Ai PhotoFlow – Master Hosting Server & Web Proofing System
 * Single-file zero-configuration client gallery host & selection sync.
 * Runs on any standard PHP 7.4 - 8.x web hosting / cPanel (No MySQL needed).
 */

ini_set('display_errors', '0');
header('X-Content-Type-Options: nosniff');
// Albums, selections and API answers change constantly: a CDN / browser must never cache this script's output
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
header('Pragma: no-cache');

// Public key of the Ai PhotoFlow License Server. Only apps holding a server-signed license token
// for a real license / trial can upload albums here. (Public key: it can verify, never create tokens.)
const APF_PUBLIC_KEY_B64 = 'ng3XTGeTg7EgnGmmLbKqqGEOXgLEI6SAoInxccNPfV8=';
const APF_ADMIN_LOGIN_URL = 'https://license.aiphotoflow.in/admin.php';

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

$DATA_DIR = __DIR__ . '/data';
if (!is_dir($DATA_DIR)) {
    @mkdir($DATA_DIR, 0777, true);
}
$GALLERIES_DIR = $DATA_DIR . '/galleries';
if (!is_dir($GALLERIES_DIR)) {
    @mkdir($GALLERIES_DIR, 0777, true);
}

// -------------------------------------------------------------
// Auto-clean: photos of an album are deleted AUTO_CLEAN_DAYS after the client submits.
// Only the preview photos (99% of the storage) are removed; gallery.json + selection.json
// (a few KB) are kept so the photographer's app can still read the client's selection.
// -------------------------------------------------------------
$AUTO_CLEAN_DAYS = 7;

function pf_dir_size($dir) {
    $total = 0;
    if (!is_dir($dir)) return 0;
    foreach (scandir($dir) as $f) {
        if ($f === '.' || $f === '..') continue;
        $path = $dir . '/' . $f;
        $total += is_dir($path) ? pf_dir_size($path) : (int)@filesize($path);
    }
    return $total;
}

function pf_delete_previews($galDir) {
    $prevDir = $galDir . '/previews';
    if (!is_dir($prevDir)) return;
    foreach (scandir($prevDir) as $f) {
        if ($f === '.' || $f === '..') continue;
        @unlink($prevDir . '/' . $f);
    }
    @rmdir($prevDir);
}

function pf_auto_clean($galleriesDir, $days, $force = false) {
    // Runs at most once per hour, triggered by normal visits (no cron job needed)
    $stamp = dirname($galleriesDir) . '/.last_clean';
    if (!$force && file_exists($stamp) && (time() - filemtime($stamp)) < 3600) return 0;
    @touch($stamp);
    $cleaned = 0;
    $limit = time() - $days * 86400;
    foreach (scandir($galleriesDir) as $item) {
        if ($item === '.' || $item === '..') continue;
        $galDir = $galleriesDir . '/' . $item;
        $gFile = $galDir . '/gallery.json';
        $sFile = $galDir . '/selection.json';
        if (!file_exists($gFile) || !file_exists($sFile)) continue;
        $g = json_decode(file_get_contents($gFile), true);
        $sel = json_decode(file_get_contents($sFile), true);
        if (!is_array($g) || !is_array($sel) || !empty($g['expired_at'])) continue;
        if (($sel['status'] ?? '') !== 'SUBMITTED' || empty($sel['submitted_at'])) continue;
        $submitted = strtotime($sel['submitted_at']);
        if ($submitted === false || $submitted > $limit) continue;
        pf_delete_previews($galDir);
        $g['expired_at'] = date('c');
        file_put_contents($gFile, json_encode($g, JSON_PRETTY_PRINT));
        $cleaned++;
    }
    return $cleaned;
}

pf_auto_clean($GALLERIES_DIR, $AUTO_CLEAN_DAYS);

$action = isset($_GET['action']) ? trim($_GET['action']) : '';

/** Verifies the X-APF-License token sent by the desktop app. Returns its payload or stops with 401. */
function pf_require_app($allowExpired = false) {
    $token = $_SERVER['HTTP_X_APF_LICENSE'] ?? '';
    $parts = explode('.', $token);
    $payload = null;
    if (count($parts) === 2 && !function_exists('sodium_crypto_sign_verify_detached')) {
        // Host has PHP sodium switched off: use the pure-PHP sodium_compat bundled with the License Server
        $compat = rtrim($_SERVER['DOCUMENT_ROOT'] ?? '', '/') . '/license/lib/sodium_compat/autoload.php';
        if (is_file($compat)) {
            require_once $compat;
            ParagonIE_Sodium_Compat::$disableFallbackForUnitTests = true;  // pure-PHP path, native is unavailable
        }
    }
    if (count($parts) === 2 && (function_exists('sodium_crypto_sign_verify_detached') || class_exists('ParagonIE_Sodium_Compat'))) {
        $sig = base64_decode(strtr($parts[1], '-_', '+/'));
        $ok = false;
        try {
            if ($sig !== false && strlen($sig) === 64) {
                $ok = class_exists('ParagonIE_Sodium_Compat', false)
                    ? ParagonIE_Sodium_Compat::crypto_sign_verify_detached($sig, $parts[0], base64_decode(APF_PUBLIC_KEY_B64))
                    : sodium_crypto_sign_verify_detached($sig, $parts[0], base64_decode(APF_PUBLIC_KEY_B64));
            }
        } catch (Throwable $e) {
            $ok = false;
        }
        if ($ok) {
            $payload = json_decode(base64_decode(strtr($parts[0], '-_', '+/')), true);
        }
    }
    $now = time();
    $ok = is_array($payload) && ($allowExpired
        || ((empty($payload['exp']) || (int)$payload['exp'] > $now) && (int)($payload['rby'] ?? 0) > $now));
    if (!$ok) {
        header('Content-Type: application/json');
        http_response_code(401);
        echo json_encode(['error' => 'A valid Ai PhotoFlow license is required to upload albums.']);
        exit;
    }
    return $payload;
}

/** Albums belong to the license (or trial computer) that created them. */
function pf_owner_of(array $payload) {
    return !empty($payload['lic']) ? 'lic:' . $payload['lic'] : 'trial:' . ($payload['mid'] ?? '');
}

function pf_check_owner($galDir, $owner) {
    $gFile = $galDir . '/gallery.json';
    if (!file_exists($gFile)) return true;
    $g = json_decode(file_get_contents($gFile), true);
    $existing = is_array($g) ? ($g['owner'] ?? '') : '';
    return $existing === '' || hash_equals($existing, $owner);
}

/** Owner is logged in to the License Server admin panel (same domain, shared secure session). */
function pf_admin_logged_in() {
    if (session_status() !== PHP_SESSION_ACTIVE) {
        session_name('APFADMIN');
        session_start(['read_and_close' => true]);
    }
    if (empty($_SESSION['apf_admin_id'])) return false;
    $fp = hash('sha256', ($_SERVER['HTTP_USER_AGENT'] ?? '') . '|' . APF_PUBLIC_KEY_B64);
    $now = time();
    return hash_equals((string)($_SESSION['apf_fp'] ?? ''), $fp)
        && $now - (int)($_SESSION['apf_last'] ?? 0) <= 1800
        && $now - (int)($_SESSION['apf_started'] ?? 0) <= 43200;
}

// -------------------------------------------------------------
// 1. API: Ping / Health Check
// -------------------------------------------------------------
if ($action === 'ping' || $action === 'status') {
    header('Content-Type: application/json');
    echo json_encode([
        'status' => 'online',
        'server' => 'Ai PhotoFlow Master Hosting',
        'version' => '1.0.0',
        'timestamp' => time()
    ]);
    exit;
}

// -------------------------------------------------------------
// 2. API: Sync Gallery from Desktop App
// -------------------------------------------------------------
if ($action === 'sync') {
    header('Content-Type: application/json');
    $raw = file_get_contents('php://input');
    $data = json_decode($raw, true);

    if (!$data || empty($data['gallery_uuid'])) {
        http_response_code(400);
        echo json_encode(['error' => 'Invalid gallery payload or missing gallery_uuid']);
        exit;
    }

    $app = pf_require_app();
    $owner = pf_owner_of($app);
    $uuid = preg_replace('/[^a-zA-Z0-9_\-]/', '', $data['gallery_uuid']);
    if ($uuid === '' || strlen($uuid) > 64) {
        http_response_code(400);
        echo json_encode(['error' => 'Invalid gallery id']);
        exit;
    }
    $galDir = $GALLERIES_DIR . '/' . $uuid;
    if (!pf_check_owner($galDir, $owner)) {
        http_response_code(403);
        echo json_encode(['error' => 'This album belongs to another account']);
        exit;
    }
    if (!is_dir($galDir)) {
        @mkdir($galDir, 0755, true);
        @mkdir($galDir . '/previews', 0755, true);
    }

    $galleryFile = $galDir . '/gallery.json';
    $old = file_exists($galleryFile) ? json_decode(file_get_contents($galleryFile), true) : null;
    if (is_array($old) && !empty($old['expired_at'])) {
        // Album was auto-cleaned and is being shared again: client gets a new selection round
        $selFile = $galDir . '/selection.json';
        if (file_exists($selFile)) {
            $sel = json_decode(file_get_contents($selFile), true);
            if (is_array($sel)) {
                $sel['status'] = 'IN_PROGRESS';
                unset($sel['submitted_at']);
                file_put_contents($selFile, json_encode($sel, JSON_PRETTY_PRINT));
            }
        }
    }
    if (!is_dir($galDir . '/previews')) {
        @mkdir($galDir . '/previews', 0777, true);
    }
    unset($data['expired_at']);
    $data['owner'] = $owner;
    $data['owner_name'] = mb_substr((string)($app['name'] ?? ''), 0, 100);
    file_put_contents($galleryFile, json_encode($data, JSON_PRETTY_PRINT));

    echo json_encode([
        'success' => true,
        'gallery_uuid' => $uuid,
        'message' => 'Gallery metadata synced successfully'
    ]);
    exit;
}

// -------------------------------------------------------------
// 3. API: Upload Preview Photo
// -------------------------------------------------------------
if ($action === 'upload_preview') {
    header('Content-Type: application/json');
    $uuid = isset($_POST['gallery_uuid']) ? preg_replace('/[^a-zA-Z0-9_\-]/', '', $_POST['gallery_uuid']) : '';
    $photoId = isset($_POST['photo_id']) ? intval($_POST['photo_id']) : 0;

    if (!$uuid || !$photoId || empty($_FILES['preview']['tmp_name'])) {
        http_response_code(400);
        echo json_encode(['error' => 'Missing uuid, photo_id, or preview file']);
        exit;
    }
    $app = pf_require_app();
    if (!file_exists($GALLERIES_DIR . '/' . $uuid . '/gallery.json') || !pf_check_owner($GALLERIES_DIR . '/' . $uuid, pf_owner_of($app))) {
        http_response_code(403);
        echo json_encode(['error' => 'Album not found for this account']);
        exit;
    }
    // Only real JPEG images up to 8 MB
    $info = @getimagesize($_FILES['preview']['tmp_name']);
    if ($_FILES['preview']['size'] > 8 * 1024 * 1024 || !$info || $info[2] !== IMAGETYPE_JPEG) {
        http_response_code(400);
        echo json_encode(['error' => 'Preview must be a JPEG image under 8 MB']);
        exit;
    }

    $galDir = $GALLERIES_DIR . '/' . $uuid . '/previews';
    if (!is_dir($galDir)) {
        @mkdir($galDir, 0755, true);
    }

    $dest = $galDir . '/' . $photoId . '.jpg';
    if (move_uploaded_file($_FILES['preview']['tmp_name'], $dest)) {
        echo json_encode(['success' => true, 'photo_id' => $photoId]);
    } else {
        http_response_code(500);
        echo json_encode(['error' => 'Failed to save preview image']);
    }
    exit;
}

// -------------------------------------------------------------
// 4. API: Update Photo Selection (from Mobile Client)
// -------------------------------------------------------------
if ($action === 'select') {
    header('Content-Type: application/json');
    $raw = file_get_contents('php://input');
    $data = json_decode($raw, true);

    if (!$data || empty($data['gallery_uuid']) || !isset($data['photo_id'])) {
        http_response_code(400);
        echo json_encode(['error' => 'Invalid selection payload']);
        exit;
    }

    $uuid = preg_replace('/[^a-zA-Z0-9_\-]/', '', $data['gallery_uuid']);
    $galDir = $GALLERIES_DIR . '/' . $uuid;
    $selFile = $galDir . '/selection.json';
    $gal = file_exists($galDir . '/gallery.json') ? json_decode(file_get_contents($galDir . '/gallery.json'), true) : null;
    $validIds = is_array($gal) ? array_map('strval', array_column($gal['photos'] ?? [], 'id')) : [];
    if (!$gal || !empty($gal['expired_at']) || !in_array(strval($data['photo_id']), $validIds, true)) {
        http_response_code(404);
        echo json_encode(['error' => 'Album or photo not found']);
        exit;
    }
    if (!empty($gal['client_pin']) && !hash_equals((string)$gal['client_pin'], (string)($data['pin'] ?? ''))) {
        http_response_code(403);
        echo json_encode(['error' => 'PIN required']);
        exit;
    }

    $selections = file_exists($selFile) ? json_decode(file_get_contents($selFile), true) : [
        'items' => [],
        'status' => 'IN_PROGRESS',
        'updated_at' => date('c')
    ];

    $pid = strval($data['photo_id']);
    $status = strtoupper($data['status'] ?? 'UNRATED');
    if (!in_array($status, ['SELECTED', 'REJECTED', 'UNRATED'], true)) $status = 'UNRATED';
    $note = mb_substr(trim((string)($data['note'] ?? '')), 0, 500);

    $selections['items'][$pid] = [
        'status' => $status,
        'note' => $note,
        'updated_at' => date('c')
    ];
    $selections['updated_at'] = date('c');

    file_put_contents($selFile, json_encode($selections, JSON_PRETTY_PRINT));

    $selectedCount = 0;
    foreach ($selections['items'] as $item) {
        if (($item['status'] ?? '') === 'SELECTED') $selectedCount++;
    }

    echo json_encode([
        'success' => true,
        'photo_id' => $pid,
        'status' => $status,
        'selected_count' => $selectedCount
    ]);
    exit;
}

// -------------------------------------------------------------
// 5. API: Submit Final Selections
// -------------------------------------------------------------
if ($action === 'submit') {
    header('Content-Type: application/json');
    $raw = file_get_contents('php://input');
    $data = json_decode($raw, true);

    if (!$data || empty($data['gallery_uuid'])) {
        http_response_code(400);
        echo json_encode(['error' => 'Missing gallery_uuid']);
        exit;
    }

    $uuid = preg_replace('/[^a-zA-Z0-9_\-]/', '', $data['gallery_uuid']);
    $galDir = $GALLERIES_DIR . '/' . $uuid;
    $selFile = $galDir . '/selection.json';
    $gal = file_exists($galDir . '/gallery.json') ? json_decode(file_get_contents($galDir . '/gallery.json'), true) : null;
    if (!$gal || !empty($gal['expired_at'])) {
        http_response_code(404);
        echo json_encode(['error' => 'Album not found']);
        exit;
    }
    if (!empty($gal['client_pin']) && !hash_equals((string)$gal['client_pin'], (string)($data['pin'] ?? ''))) {
        http_response_code(403);
        echo json_encode(['error' => 'PIN required']);
        exit;
    }

    $selections = file_exists($selFile) ? json_decode(file_get_contents($selFile), true) : ['items' => []];
    $selections['status'] = 'SUBMITTED';
    $selections['submitted_at'] = date('c');
    $selections['client_notes'] = mb_substr(trim((string)($data['notes'] ?? '')), 0, 2000);

    file_put_contents($selFile, json_encode($selections, JSON_PRETTY_PRINT));

    echo json_encode([
        'success' => true,
        'status' => 'SUBMITTED',
        'message' => 'Selections submitted successfully to photographer'
    ]);
    exit;
}

// -------------------------------------------------------------
// 6. API: Get Selections (Sync back to Desktop App)
// -------------------------------------------------------------
if ($action === 'get_selections') {
    header('Content-Type: application/json');
    $uuid = isset($_GET['id']) ? preg_replace('/[^a-zA-Z0-9_\-]/', '', $_GET['id']) : '';
    if (!$uuid) {
        http_response_code(400);
        echo json_encode(['error' => 'Missing id parameter']);
        exit;
    }

    $galDir = $GALLERIES_DIR . '/' . $uuid;
    $app = pf_require_app(true);
    if (!pf_check_owner($galDir, pf_owner_of($app))) {
        http_response_code(403);
        echo json_encode(['error' => 'This album belongs to another account']);
        exit;
    }
    $selFile = $galDir . '/selection.json';
    if (!file_exists($selFile)) {
        echo json_encode(['status' => 'ACTIVE', 'items' => [], 'selected_count' => 0]);
        exit;
    }

    $selections = json_decode(file_get_contents($selFile), true);
    $selectedCount = 0;
    foreach (($selections['items'] ?? []) as $item) {
        if (($item['status'] ?? '') === 'SELECTED') $selectedCount++;
    }
    $selections['selected_count'] = $selectedCount;
    $gInfo = file_exists($galDir . '/gallery.json') ? json_decode(file_get_contents($galDir . '/gallery.json'), true) : [];
    $selections['expired'] = !empty($gInfo['expired_at']);
    $selections['expired_at'] = $gInfo['expired_at'] ?? null;

    echo json_encode($selections);
    exit;
}

// -------------------------------------------------------------
// 7. Photographer Admin Dashboard (?admin=1)
// -------------------------------------------------------------
if (isset($_GET['admin'])) {
    header('X-Frame-Options: DENY');
    header('Cache-Control: no-store, private');
    if (!pf_admin_logged_in()) {
        header('Location: ' . APF_ADMIN_LOGIN_URL, true, 302);
        exit;
    }

    // List all galleries
    $albums = [];
    if (is_dir($GALLERIES_DIR)) {
        foreach (scandir($GALLERIES_DIR) as $item) {
            if ($item === '.' || $item === '..') continue;
            $gPath = $GALLERIES_DIR . '/' . $item . '/gallery.json';
            $sPath = $GALLERIES_DIR . '/' . $item . '/selection.json';
            if (file_exists($gPath)) {
                $gData = json_decode(file_get_contents($gPath), true);
                $sData = file_exists($sPath) ? json_decode(file_get_contents($sPath), true) : ['status' => 'SELECTING', 'items' => []];
                $selCount = 0;
                foreach (($sData['items'] ?? []) as $it) {
                    if (($it['status'] ?? '') === 'SELECTED') $selCount++;
                }
                $albums[] = [
                    'uuid' => $item,
                    'title' => $gData['title'] ?? 'Untitled Shoot',
                    'client' => $gData['client_name'] ?? 'Client',
                    'total' => count($gData['photos'] ?? []),
                    'selected' => $selCount,
                    'status' => $sData['status'] ?? 'SELECTING',
                    'pin' => $gData['client_pin'] ?? '',
                    'updated_at' => $sData['updated_at'] ?? ($gData['created_at'] ?? 'Recently'),
                    'expired_at' => $gData['expired_at'] ?? null,
                    'clean_on' => (($sData['status'] ?? '') === 'SUBMITTED' && !empty($sData['submitted_at']) && strtotime($sData['submitted_at']))
                        ? date('d M Y', strtotime($sData['submitted_at']) + $AUTO_CLEAN_DAYS * 86400) : null,
                    'size' => pf_dir_size($GALLERIES_DIR . '/' . $item)
                ];
            }
        }
    }
    ?>
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Ai PhotoFlow – Master Album Dashboard</title>
        <style>
            body { background: #0b0e14; color: #fff; font-family: -apple-system, sans-serif; padding: 25px; margin: 0; }
            .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #1f2638; padding-bottom: 15px; margin-bottom: 25px; }
            table { width: 100%; border-collapse: collapse; background: #121723; border-radius: 8px; overflow: hidden; border: 1px solid #20283b; }
            th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #1a2233; font-size: 13px; }
            th { background: #161d2d; color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 11px; }
            .badge { padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
            .badge-sub { background: rgba(16, 185, 129, 0.2); color: #34d399; }
            .badge-sel { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
            a { color: #38bdf8; text-decoration: none; }
        </style>
    </head>
    <body>
        <div class="header">
            <div>
                <h1 style="margin: 0; font-size: 20px;">✨ Ai PhotoFlow – Master Hosting Albums</h1>
                <p style="margin: 4px 0 0; color: #94a3b8; font-size: 12px;">All active client proofing albums hosted on your domain</p>
            </div>
            <div>
                <span class="badge badge-sub">Total Albums: <?= count($albums) ?></span>
                <span class="badge badge-sel">Storage used: <?= round(array_sum(array_column($albums, 'size')) / 1048576, 1) ?> MB</span>
                <div style="color: #64748b; font-size: 11px; margin-top: 6px;">🧹 Auto-clean: photos are deleted <?= $AUTO_CLEAN_DAYS ?> days after the client submits (selection list is kept)</div>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Album / Project</th>
                    <th>Client Name</th>
                    <th>Total Photos</th>
                    <th>Selected (❤️)</th>
                    <th>Status</th>
                    <th>Security PIN</th>
                    <th>Storage</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                <?php if (empty($albums)): ?>
                <tr>
                    <td colspan="8" style="text-align: center; color: #64748b; padding: 30px;">
                        No albums created yet. Open Ai PhotoFlow software and click "📱 Client Link" to create your first album!
                    </td>
                </tr>
                <?php else: foreach ($albums as $a): ?>
                <tr>
                    <td><strong><?= htmlspecialchars($a['title']) ?></strong></td>
                    <td><?= htmlspecialchars($a['client']) ?></td>
                    <td><?= $a['total'] ?></td>
                    <td><strong style="color: #f43f5e;"><?= $a['selected'] ?></strong></td>
                    <td>
                        <?php if ($a['expired_at']): ?>
                        <span class="badge" style="background: rgba(148, 163, 184, 0.15); color: #94a3b8;">🧹 Photos cleaned</span>
                        <?php else: ?>
                        <span class="badge <?= $a['status'] === 'SUBMITTED' ? 'badge-sub' : 'badge-sel' ?>">
                            <?= $a['status'] === 'SUBMITTED' ? '✓ Submitted' : '⏳ In Progress' ?>
                        </span>
                        <?php if ($a['clean_on']): ?>
                        <div style="color: #64748b; font-size: 11px; margin-top: 4px;">Auto-clean: <?= htmlspecialchars($a['clean_on']) ?></div>
                        <?php endif; ?>
                        <?php endif; ?>
                    </td>
                    <td><code><?= htmlspecialchars($a['pin'] ?: 'None') ?></code></td>
                    <td><?= $a['size'] >= 1048576 ? round($a['size'] / 1048576, 1) . ' MB' : max(1, round($a['size'] / 1024)) . ' KB' ?></td>
                    <td>
                        <a href="?id=<?= urlencode($a['uuid']) ?><?= $a['pin'] ? '&pin=' . urlencode($a['pin']) : '' ?>" target="_blank">View Album ↗</a>
                    </td>
                </tr>
                <?php endforeach; endif; ?>
            </tbody>
        </table>
    </body>
    </html>
    <?php
    exit;
}

// -------------------------------------------------------------
// 8. Public Client Gallery View (?id=UUID)
// -------------------------------------------------------------
$uuid = isset($_GET['id']) ? preg_replace('/[^a-zA-Z0-9_\-]/', '', $_GET['id']) : '';

if (!$uuid) {
    ?>
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Ai PhotoFlow – Client Gallery Host</title>
        <style>
            body { background: #0b0e14; color: #fff; font-family: -apple-system, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; text-align: center; }
            .card { background: #131824; border: 1px solid #232c42; padding: 35px; border-radius: 12px; max-width: 420px; }
            h1 { font-size: 20px; margin: 0 0 10px; }
            p { font-size: 13px; color: #94a3b8; line-height: 1.5; }
            a { color: #38bdf8; text-decoration: none; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>📸 Ai PhotoFlow Master Hosting</h1>
            <p>Your web hosting server is active and ready to host client proofing albums.</p>
            <p style="margin-top: 20px;">Photographer: <a href="?admin=1">Open Admin Dashboard</a></p>
        </div>
    </body>
    </html>
    <?php
    exit;
}

$galDir = $GALLERIES_DIR . '/' . $uuid;
$galFile = $galDir . '/gallery.json';
$selFile = $galDir . '/selection.json';

if (!file_exists($galFile)) {
    http_response_code(404);
    echo "<h1>404 – Gallery Not Found</h1><p>This album link does not exist or has been removed.</p>";
    exit;
}

$gallery = json_decode(file_get_contents($galFile), true);
$selections = file_exists($selFile) ? json_decode(file_get_contents($selFile), true) : ['items' => []];

if (!empty($gallery['expired_at'])) {
    $selCountDone = 0;
    foreach (($selections['items'] ?? []) as $it) {
        if (($it['status'] ?? '') === 'SELECTED') $selCountDone++;
    }
    ?>
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title><?= htmlspecialchars($gallery['title'] ?? 'Album') ?> – Selection Complete</title>
        <style>
            body { background: #090c10; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 16px; box-sizing: border-box; text-align: center; }
            .card { background: #111520; border: 1px solid #21283b; padding: 32px 24px; border-radius: 16px; max-width: 380px; }
            p { color: #94a3b8; font-size: 13px; line-height: 1.6; }
        </style>
    </head>
    <body>
        <div class="card">
            <div style="font-size: 42px; margin-bottom: 8px;">✅</div>
            <h2 style="margin: 0; font-size: 18px;"><?= htmlspecialchars($gallery['title'] ?? 'Album') ?></h2>
            <p>Aapki photo selection (<?= $selCountDone ?> photos) photographer tak pahunch chuki hai. Ye link ab band ho gaya hai.</p>
            <p>Your selection has been received by the photographer. This preview link has expired.</p>
        </div>
    </body>
    </html>
    <?php
    exit;
}

$clientPin = $gallery['client_pin'] ?? '';
$userPin = $_GET['pin'] ?? ($_POST['pin'] ?? '');

if ($clientPin && $userPin !== $clientPin) {
    ?>
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title><?= htmlspecialchars($gallery['title']) ?> – Security PIN</title>
        <style>
            body { background: #090c10; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
            .lock-card { background: #111520; border: 1px solid #21283b; padding: 35px 25px; border-radius: 16px; width: 330px; text-align: center; box-shadow: 0 20px 40px rgba(0,0,0,0.7); }
            input { width: 100%; box-sizing: border-box; padding: 12px; background: #07090e; border: 1.5px solid #2e3a54; border-radius: 8px; color: #fff; font-size: 18px; text-align: center; letter-spacing: 4px; margin: 18px 0; outline: none; }
            input:focus { border-color: #3b82f6; }
            button { width: 100%; padding: 12px; background: #2563eb; color: #fff; border: none; border-radius: 8px; font-size: 15px; font-weight: bold; cursor: pointer; }
        </style>
    </head>
    <body>
        <div class="lock-card">
            <div style="font-size: 40px; margin-bottom: 10px;">🔒</div>
            <h2 style="margin: 0; font-size: 18px;"><?= htmlspecialchars($gallery['title']) ?></h2>
            <p style="color: #94a3b8; font-size: 12px; margin: 8px 0 0;">Please enter your 4-digit PIN to access this private gallery:</p>
            <form method="GET">
                <input type="hidden" name="id" value="<?= htmlspecialchars($uuid) ?>">
                <input type="password" name="pin" maxlength="10" placeholder="••••" autofocus required>
                <button type="submit">Open Gallery</button>
            </form>
        </div>
    </body>
    </html>
    <?php
    exit;
}

$photos = $gallery['photos'] ?? [];
$watermarkText = $gallery['watermark_text'] ?? 'PROOF ONLY';
$isWatermark = !empty($gallery['watermark_enabled']);
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title><?= htmlspecialchars($gallery['title']) ?> – Client Proofing</title>
    <style>
        :root { --primary: #2563eb; --accent: #f43f5e; --bg: #090c10; --card: #121622; --border: #1e2638; --text: #f8fafc; }
        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding-bottom: 90px; }
        header { position: sticky; top: 0; z-index: 100; background: rgba(9, 12, 16, 0.95); backdrop-filter: blur(10px); border-bottom: 1px solid var(--border); padding: 12px 18px; display: flex; justify-content: space-between; align-items: center; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; padding: 14px; }
        @media (max-width: 600px) { .grid { grid-template-columns: repeat(2, 1fr); gap: 8px; padding: 8px; } }
        .card { background: var(--card); border: 1.5px solid var(--border); border-radius: 10px; overflow: hidden; position: relative; transition: border-color 0.2s; }
        .card.is-selected { border-color: #f43f5e; box-shadow: 0 0 15px rgba(244, 63, 94, 0.35); }
        .card.is-rejected { opacity: 0.45; filter: grayscale(80%); }
        .img-wrap { position: relative; width: 100%; aspect-ratio: 3/2; background: #06080c; overflow: hidden; }
        .img-wrap img { width: 100%; height: 100%; object-fit: contain; }
        .watermark { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; pointer-events: none; font-size: 13px; font-weight: 800; color: rgba(255,255,255,0.22); letter-spacing: 2px; text-transform: uppercase; transform: rotate(-25deg); user-select: none; }
        .actions { display: flex; gap: 6px; padding: 8px; background: #0e121a; }
        .btn-act { flex: 1; padding: 7px 4px; border-radius: 6px; border: 1px solid #232c40; background: #151b27; color: #94a3b8; font-size: 12px; font-weight: 700; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 4px; }
        .btn-sel.active { background: #f43f5e; color: #fff; border-color: #f43f5e; }
        .btn-rej.active { background: #374151; color: #fff; }
        .bottom-bar { position: fixed; bottom: 0; left: 0; right: 0; z-index: 100; background: rgba(14, 18, 26, 0.98); border-top: 1px solid var(--border); padding: 12px 18px; display: flex; justify-content: space-between; align-items: center; backdrop-filter: blur(12px); }
        .btn-submit { background: linear-gradient(135deg, #10b981, #059669); color: #fff; border: none; padding: 10px 20px; border-radius: 8px; font-weight: 800; font-size: 13px; cursor: pointer; }
        .img-wrap { cursor: zoom-in; }
        .img-wrap img, .viewer img { -webkit-user-select: none; user-select: none; -webkit-touch-callout: none; -webkit-user-drag: none; }
        .zoom-hint { position: absolute; top: 8px; right: 8px; width: 30px; height: 30px; border-radius: 50%; background: rgba(0,0,0,0.55); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 15px; pointer-events: none; }

        /* Full screen photo viewer */
        .viewer { position: fixed; inset: 0; z-index: 1000; background: #000; display: none; flex-direction: column; height: 100vh; height: 100dvh; touch-action: none; }
        .viewer.open { display: flex; }
        .viewer-top { display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; padding-top: max(10px, env(safe-area-inset-top)); color: #e2e8f0; font-size: 13px; font-weight: 700; z-index: 2; background: linear-gradient(180deg, rgba(0,0,0,0.75), rgba(0,0,0,0)); }
        .viewer-btn { background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.18); color: #fff; width: 40px; height: 40px; border-radius: 50%; font-size: 18px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        .viewer-stage { position: relative; flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; overflow: hidden; }
        .viewer-stage img { max-width: 100%; max-height: 100%; width: auto; height: auto; object-fit: contain; transition: transform 0.2s ease; transform-origin: center center; }
        .viewer-stage img.zoomed { cursor: grab; transition: none; }
        .viewer-nav { position: absolute; top: 50%; transform: translateY(-50%); width: 48px; height: 48px; font-size: 24px; z-index: 2; }
        .viewer-nav.prev { left: 12px; }
        .viewer-nav.next { right: 12px; }
        .viewer-bottom { display: flex; gap: 10px; justify-content: center; padding: 12px 14px; padding-bottom: max(12px, env(safe-area-inset-bottom)); background: linear-gradient(0deg, rgba(0,0,0,0.85), rgba(0,0,0,0)); z-index: 2; }
        .viewer-bottom .btn-act { flex: 0 1 180px; padding: 12px 8px; font-size: 14px; }
        @media (max-width: 600px) { .viewer-nav { display: none; } }
    </style>
</head>
<body>
    <header>
        <div>
            <h1 style="margin: 0; font-size: 15px; font-weight: 800;"><?= htmlspecialchars($gallery['title']) ?></h1>
            <span style="font-size: 11px; color: #94a3b8;">Client: <?= htmlspecialchars($gallery['client_name'] ?: 'Wedding') ?></span>
        </div>
        <div>
            <span id="counterBadge" style="font-size: 12px; background: rgba(244, 63, 94, 0.2); color: #f43f5e; border: 1px solid #f43f5e; padding: 3px 9px; border-radius: 12px; font-weight: bold;">
                ❤️ <span id="selCount">0</span> / <?= count($photos) ?>
            </span>
        </div>
    </header>

    <div class="grid">
        <?php foreach ($photos as $p): 
            $pid = strval($p['id']);
            $selState = $selections['items'][$pid]['status'] ?? 'UNRATED';
            $previewUrl = "data/galleries/{$uuid}/previews/{$pid}.jpg";
            if (!file_exists(__DIR__ . '/' . $previewUrl)) {
                $previewUrl = $p['url'] ?? '';
            }
        ?>
        <div class="card <?= $selState === 'SELECTED' ? 'is-selected' : ($selState === 'REJECTED' ? 'is-rejected' : '') ?>" id="card-<?= $pid ?>">
            <div class="img-wrap" onclick="openViewer(<?= $pid ?>)">
                <img src="<?= htmlspecialchars($previewUrl) ?>" alt="Photo <?= htmlspecialchars($p['filename'] ?? '') ?>" loading="lazy" draggable="false">
                <span class="zoom-hint">⤢</span>
                <?php if ($isWatermark): ?>
                <div class="watermark"><?= htmlspecialchars($watermarkText) ?></div>
                <?php endif; ?>
            </div>
            <div class="actions">
                <button type="button" class="btn-act btn-sel <?= $selState === 'SELECTED' ? 'active' : '' ?>" onclick="handleSelect(<?= $pid ?>, 'SELECTED')">
                    ❤️ Select
                </button>
                <button type="button" class="btn-act btn-rej <?= $selState === 'REJECTED' ? 'active' : '' ?>" onclick="handleSelect(<?= $pid ?>, 'REJECTED')">
                    ✕ Reject
                </button>
            </div>
        </div>
        <?php endforeach; ?>
    </div>

    <div class="bottom-bar">
        <div>
            <div style="font-size: 12px; color: #94a3b8;">Selected Photos: <strong id="bottomCount" style="color: #f43f5e; font-size: 14px;">0</strong></div>
            <div style="font-size: 10px; color: #64748b;">Tap ❤️ on your favorites for album design</div>
        </div>
        <button type="button" class="btn-submit" onclick="submitFinal()">
            ✓ Submit Selection
        </button>
    </div>

    <!-- Full screen viewer: tap a photo to open, swipe / arrow keys to move, double-tap to zoom -->
    <div class="viewer" id="viewer" aria-hidden="true">
        <div class="viewer-top">
            <span id="viewerCounter">1 / 1</span>
            <div style="display: flex; gap: 8px;">
                <button type="button" class="viewer-btn" id="viewerFsBtn" onclick="toggleBrowserFullscreen()" title="Full screen">⛶</button>
                <button type="button" class="viewer-btn" onclick="closeViewer()" title="Close">✕</button>
            </div>
        </div>
        <div class="viewer-stage" id="viewerStage">
            <button type="button" class="viewer-btn viewer-nav prev" onclick="stepViewer(-1)" title="Previous">‹</button>
            <img id="viewerImg" alt="" draggable="false">
            <button type="button" class="viewer-btn viewer-nav next" onclick="stepViewer(1)" title="Next">›</button>
        </div>
        <div class="viewer-bottom">
            <button type="button" class="btn-act btn-sel" id="viewerSel" onclick="viewerSelect('SELECTED')">❤️ Select</button>
            <button type="button" class="btn-act btn-rej" id="viewerRej" onclick="viewerSelect('REJECTED')">✕ Reject</button>
        </div>
    </div>

    <script>
        const GALLERY_UUID = <?= json_encode($uuid) ?>;
        const CLIENT_PIN = <?= json_encode((string)$userPin) ?>;
        let selections = <?= json_encode($selections['items'] ?? (object)[]) ?>;

        function updateCounter() {
            let count = 0;
            for (let k in selections) {
                if (selections[k].status === 'SELECTED') count++;
            }
            document.getElementById('selCount').innerText = count;
            document.getElementById('bottomCount').innerText = count;
        }
        updateCounter();

        async function handleSelect(photoId, newStatus) {
            const current = selections[photoId]?.status;
            const updated = (current === newStatus) ? 'UNRATED' : newStatus;

            selections[photoId] = { status: updated };
            const card = document.getElementById('card-' + photoId);
            const btnSel = card.querySelector('.btn-sel');
            const btnRej = card.querySelector('.btn-rej');

            card.classList.remove('is-selected', 'is-rejected');
            btnSel.classList.remove('active');
            btnRej.classList.remove('active');

            if (updated === 'SELECTED') {
                card.classList.add('is-selected');
                btnSel.classList.add('active');
            } else if (updated === 'REJECTED') {
                card.classList.add('is-rejected');
                btnRej.classList.add('active');
            }

            updateCounter();
            syncViewerButtons();

            try {
                await fetch('?action=select', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ gallery_uuid: GALLERY_UUID, photo_id: photoId, status: updated, pin: CLIENT_PIN })
                });
            } catch (e) {
                console.error(e);
            }
        }

        // ---------------- Full screen viewer ----------------
        const PHOTOS = Array.from(document.querySelectorAll('.card')).map(c => ({
            id: parseInt(c.id.replace('card-', ''), 10),
            src: c.querySelector('.img-wrap img').getAttribute('src')
        }));
        const viewer = document.getElementById('viewer');
        const viewerImg = document.getElementById('viewerImg');
        let vIndex = 0;
        let zoom = { on: false, x: 0, y: 0, startX: 0, startY: 0, baseX: 0, baseY: 0 };

        function openViewer(photoId) {
            const i = PHOTOS.findIndex(p => p.id === photoId);
            if (i < 0) return;
            vIndex = i;
            viewer.classList.add('open');
            viewer.setAttribute('aria-hidden', 'false');
            document.body.style.overflow = 'hidden';
            showViewerPhoto();
            // Real browser full screen where supported (PC, Android); iPhone keeps the full-window viewer
            enterBrowserFullscreen();
        }

        function closeViewer() {
            viewer.classList.remove('open');
            viewer.setAttribute('aria-hidden', 'true');
            document.body.style.overflow = '';
            resetZoom();
            if (document.fullscreenElement || document.webkitFullscreenElement) toggleBrowserFullscreen();
            const card = document.getElementById('card-' + PHOTOS[vIndex].id);
            if (card) card.scrollIntoView({ block: 'center' });
        }

        function enterBrowserFullscreen() {
            const el = document.documentElement;
            const req = el.requestFullscreen || el.webkitRequestFullscreen;
            if (req && !(document.fullscreenElement || document.webkitFullscreenElement)) {
                try { const r = req.call(el); if (r && r.catch) r.catch(() => {}); } catch (e) {}
            }
        }

        function toggleBrowserFullscreen() {
            if (document.fullscreenElement || document.webkitFullscreenElement) {
                const ex = document.exitFullscreen || document.webkitExitFullscreen;
                try { const r = ex.call(document); if (r && r.catch) r.catch(() => {}); } catch (e) {}
            } else {
                enterBrowserFullscreen();
            }
        }
        if (!(document.documentElement.requestFullscreen || document.documentElement.webkitRequestFullscreen)) {
            document.getElementById('viewerFsBtn').style.display = 'none';
        }

        function showViewerPhoto() {
            resetZoom();
            const p = PHOTOS[vIndex];
            viewerImg.src = p.src;
            document.getElementById('viewerCounter').innerText = (vIndex + 1) + ' / ' + PHOTOS.length;
            syncViewerButtons();
            // Preload neighbours for instant next / previous
            [vIndex - 1, vIndex + 1].forEach(i => { if (PHOTOS[i]) { const im = new Image(); im.src = PHOTOS[i].src; } });
        }

        function stepViewer(dir) {
            const n = vIndex + dir;
            if (n < 0 || n >= PHOTOS.length) return;
            vIndex = n;
            showViewerPhoto();
        }

        function syncViewerButtons() {
            if (!viewer.classList.contains('open')) return;
            const st = selections[PHOTOS[vIndex].id]?.status;
            document.getElementById('viewerSel').classList.toggle('active', st === 'SELECTED');
            document.getElementById('viewerRej').classList.toggle('active', st === 'REJECTED');
        }

        function viewerSelect(status) {
            handleSelect(PHOTOS[vIndex].id, status);
        }

        // Zoom: double-tap / double-click toggles 2.5x at that point, drag to pan
        function resetZoom() {
            zoom = { on: false, x: 0, y: 0, startX: 0, startY: 0, baseX: 0, baseY: 0 };
            viewerImg.classList.remove('zoomed');
            viewerImg.style.transform = '';
        }
        function applyZoom() {
            viewerImg.style.transform = zoom.on ? `translate(${zoom.x}px, ${zoom.y}px) scale(2.5)` : '';
        }
        function toggleZoomAt(clientX, clientY) {
            if (zoom.on) { resetZoom(); return; }
            const r = viewerImg.getBoundingClientRect();
            zoom.on = true;
            zoom.x = (r.left + r.width / 2 - clientX) * 1.5;
            zoom.y = (r.top + r.height / 2 - clientY) * 1.5;
            viewerImg.classList.add('zoomed');
            applyZoom();
        }
        viewerImg.addEventListener('dblclick', e => toggleZoomAt(e.clientX, e.clientY));

        let touch = null, lastTap = 0;
        const stage = document.getElementById('viewerStage');
        stage.addEventListener('touchstart', e => {
            if (e.touches.length !== 1) { touch = null; return; }
            const t = e.touches[0];
            touch = { x: t.clientX, y: t.clientY, time: Date.now() };
            zoom.baseX = zoom.x; zoom.baseY = zoom.y;
        }, { passive: true });
        stage.addEventListener('touchmove', e => {
            if (!touch || !zoom.on || e.touches.length !== 1) return;
            const t = e.touches[0];
            zoom.x = zoom.baseX + (t.clientX - touch.x);
            zoom.y = zoom.baseY + (t.clientY - touch.y);
            applyZoom();
        }, { passive: true });
        stage.addEventListener('touchend', e => {
            if (!touch) return;
            const t = e.changedTouches[0];
            const dx = t.clientX - touch.x, dy = t.clientY - touch.y;
            const now = Date.now();
            if (Math.abs(dx) < 10 && Math.abs(dy) < 10) {
                if (now - lastTap < 300) { toggleZoomAt(t.clientX, t.clientY); lastTap = 0; }
                else lastTap = now;
            } else if (!zoom.on && Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.2) {
                stepViewer(dx < 0 ? 1 : -1);
            } else if (!zoom.on && dy > 90 && Math.abs(dy) > Math.abs(dx) * 1.5) {
                closeViewer();  // swipe down to close
            }
            touch = null;
        });

        // Mouse drag to pan when zoomed (PC)
        let drag = null;
        viewerImg.addEventListener('mousedown', e => {
            if (!zoom.on) return;
            e.preventDefault();
            drag = { x: e.clientX, y: e.clientY, bx: zoom.x, by: zoom.y };
        });
        window.addEventListener('mousemove', e => {
            if (!drag) return;
            zoom.x = drag.bx + (e.clientX - drag.x);
            zoom.y = drag.by + (e.clientY - drag.y);
            applyZoom();
        });
        window.addEventListener('mouseup', () => { drag = null; });

        document.addEventListener('keydown', e => {
            if (!viewer.classList.contains('open')) return;
            if (e.key === 'ArrowRight') stepViewer(1);
            else if (e.key === 'ArrowLeft') stepViewer(-1);
            else if (e.key === 'Escape') closeViewer();
        });

        // Download protection: no right-click / long-press save on photos
        document.addEventListener('contextmenu', e => { if (e.target.tagName === 'IMG') e.preventDefault(); });

        async function submitFinal() {
            const count = document.getElementById('selCount').innerText;
            if (count === '0') {
                alert('Please select at least 1 photo before submitting.');
                return;
            }
            if (!confirm(`Are you sure you want to submit your ${count} selected photos to the photographer?`)) return;

            try {
                const res = await fetch('?action=submit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ gallery_uuid: GALLERY_UUID, pin: CLIENT_PIN })
                });
                const data = await res.json();
                if (data.success) {
                    alert('🎉 Thank you! Your photo selection has been successfully sent to the photographer.');
                }
            } catch (e) {
                alert('Selection submitted!');
            }
        }
    </script>
</body>
</html>
