<?php
/**
 * Ai PhotoFlow – Master Hosting Server & Web Proofing System
 * Single-file zero-configuration client gallery host & selection sync.
 * Runs on any standard PHP 7.4 - 8.x web hosting / cPanel (No MySQL needed).
 */

header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization, X-Requested-With');

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

$action = isset($_GET['action']) ? trim($_GET['action']) : '';

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

    $uuid = preg_replace('/[^a-zA-Z0-9_\-]/', '', $data['gallery_uuid']);
    $galDir = $GALLERIES_DIR . '/' . $uuid;
    if (!is_dir($galDir)) {
        @mkdir($galDir, 0777, true);
        @mkdir($galDir . '/previews', 0777, true);
    }

    $galleryFile = $galDir . '/gallery.json';
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

    $galDir = $GALLERIES_DIR . '/' . $uuid . '/previews';
    if (!is_dir($galDir)) {
        @mkdir($galDir, 0777, true);
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

    $selections = file_exists($selFile) ? json_decode(file_get_contents($selFile), true) : [
        'items' => [],
        'status' => 'IN_PROGRESS',
        'updated_at' => date('c')
    ];

    $pid = strval($data['photo_id']);
    $status = strtoupper($data['status'] ?? 'UNRATED');
    $note = trim($data['note'] ?? '');

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

    $selections = file_exists($selFile) ? json_decode(file_get_contents($selFile), true) : ['items' => []];
    $selections['status'] = 'SUBMITTED';
    $selections['submitted_at'] = date('c');
    $selections['client_notes'] = trim($data['notes'] ?? '');

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

    echo json_encode($selections);
    exit;
}

// -------------------------------------------------------------
// 7. Photographer Admin Dashboard (?admin=1)
// -------------------------------------------------------------
if (isset($_GET['admin'])) {
    $pin = $_GET['pin'] ?? '';
    $ADMIN_PIN = '1234'; // Default photographer PIN

    if ($pin !== $ADMIN_PIN) {
        ?>
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Ai PhotoFlow – Admin Login</title>
            <style>
                body { background: #0b0e14; color: #fff; font-family: -apple-system, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
                .box { background: #131824; border: 1px solid #232c42; padding: 30px; border-radius: 12px; width: 320px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
                input { width: 100%; box-sizing: border-box; padding: 10px; background: #0a0d14; border: 1px solid #2a354d; border-radius: 6px; color: #fff; font-size: 16px; margin: 15px 0; text-align: center; }
                button { width: 100%; padding: 12px; background: #2563eb; color: #fff; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; }
            </style>
        </head>
        <body>
            <div class="box">
                <h2 style="margin: 0 0 10px; font-size: 18px;">🔐 Photographer Admin</h2>
                <p style="color: #94a3b8; font-size: 12px; margin: 0;">Enter Admin PIN to view all albums</p>
                <form method="GET">
                    <input type="hidden" name="admin" value="1">
                    <input type="password" name="pin" placeholder="Enter PIN (Default: 1234)" autofocus required>
                    <button type="submit">Unlock Dashboard</button>
                </form>
            </div>
        </body>
        </html>
        <?php
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
                    'updated_at' => $sData['updated_at'] ?? ($gData['created_at'] ?? 'Recently')
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
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                <?php if (empty($albums)): ?>
                <tr>
                    <td colspan="7" style="text-align: center; color: #64748b; padding: 30px;">
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
                        <span class="badge <?= $a['status'] === 'SUBMITTED' ? 'badge-sub' : 'badge-sel' ?>">
                            <?= $a['status'] === 'SUBMITTED' ? '✓ Submitted' : '⏳ In Progress' ?>
                        </span>
                    </td>
                    <td><code><?= htmlspecialchars($a['pin'] ?: 'None') ?></code></td>
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
            <div class="img-wrap">
                <img src="<?= htmlspecialchars($previewUrl) ?>" alt="Photo <?= htmlspecialchars($p['filename'] ?? '') ?>" loading="lazy">
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

    <script>
        const GALLERY_UUID = <?= json_encode($uuid) ?>;
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

            try {
                await fetch('?action=select', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ gallery_uuid: GALLERY_UUID, photo_id: photoId, status: updated })
                });
            } catch (e) {
                console.error(e);
            }
        }

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
                    body: JSON.stringify({ gallery_uuid: GALLERY_UUID })
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
