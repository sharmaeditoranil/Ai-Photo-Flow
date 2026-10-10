import React, { useEffect, useState } from 'react';
import { ChevronDown, ChevronRight, Eye, EyeOff, RotateCcw, Sparkles, Wand2 } from 'lucide-react';
import { api } from '../api';
import type { EditParameters, RetouchParams, RetouchPreset } from '../types';

type SectionKey = 'heal' | 'mattifier' | 'skinMask' | 'skinDetails' | 'imperfections' | 'skinTone';

let presetCache: { presets: RetouchPreset[]; defaults: RetouchParams } | null = null;

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));

interface SliderDef {
  key: string;
  label: string;
  min: number;
  max: number;
  hint?: string;
}

const SECTIONS: { key: SectionKey; title: string; hindi: string; toggle: boolean; sliders: SliderDef[] }[] = [
  {
    key: 'heal', title: 'AI Heal', hindi: 'पिंपल / दाग हटाएं', toggle: true,
    sliders: [
      { key: 'opacity', label: 'Opacity', min: 0, max: 100 },
      { key: 'strength', label: 'Detection Strength', min: 0, max: 100, hint: 'Higher = more spots healed' },
    ],
  },
  {
    key: 'mattifier', title: 'AI Mattifier', hindi: 'ऑयली शाइन हटाएं', toggle: true,
    sliders: [
      { key: 'opacity', label: 'Opacity', min: 0, max: 100 },
      { key: 'strength', label: 'Strength', min: 0, max: 100 },
      { key: 'keepSheen', label: 'Keep Natural Sheen', min: 0, max: 100 },
      { key: 'texturePreserve', label: 'Texture Preserve', min: 0, max: 100 },
    ],
  },
  {
    key: 'skinMask', title: 'Skin Mask', hindi: 'सिर्फ स्किन', toggle: false,
    sliders: [
      { key: 'tolerance', label: 'Tolerance', min: 0, max: 100 },
      { key: 'feather', label: 'Feather', min: 0, max: 100 },
      { key: 'opacity', label: 'Opacity', min: 0, max: 100 },
    ],
  },
  {
    key: 'skinDetails', title: 'Skin Details (Smoothing)', hindi: 'स्किन स्मूथनेस', toggle: true,
    sliders: [
      { key: 'amount', label: 'Amount', min: 0, max: 100 },
      { key: 'fine', label: 'Fine (pores)', min: -100, max: 100, hint: '− keeps pores' },
      { key: 'medium', label: 'Medium (blotches)', min: -100, max: 100 },
      { key: 'coarse', label: 'Coarse (tones)', min: -100, max: 100 },
      { key: 'balance', label: 'Balance (dark ↔ bright)', min: -100, max: 100 },
      { key: 'portraitSize', label: 'Portrait Size', min: 0, max: 100 },
    ],
  },
  {
    key: 'imperfections', title: 'Skin Imperfections', hindi: 'रेडनेस / आई बैग्स', toggle: true,
    sliders: [
      { key: 'evenTone', label: 'Even Skin Tone', min: 0, max: 100 },
      { key: 'redness', label: 'Redness', min: 0, max: 100 },
      { key: 'redBrightness', label: 'Red Brightness', min: 0, max: 100 },
      { key: 'yellow', label: 'Yellow', min: 0, max: 100 },
      { key: 'yellowBrightness', label: 'Yellow Brightness', min: 0, max: 100 },
      { key: 'balance', label: 'Balance (red ↔ yellow)', min: -100, max: 100 },
      { key: 'eyeBags', label: 'Reduce Eye Bags', min: 0, max: 100 },
    ],
  },
  {
    key: 'skinTone', title: 'Skin Tone', hindi: 'स्किन टोन', toggle: true,
    sliders: [
      { key: 'hue', label: 'Hue', min: -100, max: 100 },
      { key: 'saturation', label: 'Saturation', min: -100, max: 100 },
      { key: 'brightness', label: 'Brightness', min: -100, max: 100 },
      { key: 'contrast', label: 'Contrast', min: -100, max: 100 },
      { key: 'shadows', label: 'Shadows', min: -100, max: 100 },
      { key: 'highlights', label: 'Highlights', min: -100, max: 100 },
    ],
  },
];

interface RetouchPanelProps {
  edits: EditParameters;
  onCommit: (retouch: RetouchParams | null) => void;
  autoEditPreset: string;
  onSelectAutoEditPreset: (name: string) => void;
}

export const RetouchPanel: React.FC<RetouchPanelProps> = ({ edits, onCommit, autoEditPreset, onSelectAutoEditPreset }) => {
  const [catalog, setCatalog] = useState(presetCache);
  const [draft, setDraft] = useState<RetouchParams | null>(edits.retouch ?? null);
  const [open, setOpen] = useState<Record<string, boolean>>({ skinDetails: true });

  useEffect(() => {
    if (presetCache) return;
    api.getRetouchPresets().then(c => { presetCache = c; setCatalog(c); }).catch(() => {});
  }, []);

  // Follow the photo / external updates (auto edit, reset, photo switch)
  useEffect(() => {
    setDraft(edits.retouch ?? null);
  }, [edits.retouch]);

  const presetParams = (name: string): RetouchParams | null =>
    catalog?.presets.find(p => p.name === name)?.params ?? null;

  const commit = (next: RetouchParams | null) => {
    setDraft(next);
    onCommit(next);
  };

  const setValue = (section: SectionKey, key: string, value: number | boolean, final: boolean) => {
    if (!draft) return;
    const next = clone(draft);
    (next[section] as any)[key] = value;
    if (final) commit(next);
    else setDraft(next);
  };

  const resetSection = (section: SectionKey) => {
    if (!draft) return;
    const base = presetParams(draft.preset) ?? catalog?.defaults;
    if (!base) return;
    const next = clone(draft);
    (next as any)[section] = clone((base as any)[section]);
    commit(next);
  };

  const applyPreset = (name: string) => {
    const p = presetParams(name);
    if (p) commit(clone(p));
  };

  const defaultFor = (section: SectionKey, key: string): number => {
    const base = (draft && presetParams(draft.preset)) ?? catalog?.defaults;
    const v = base ? (base as any)[section]?.[key] : 0;
    return typeof v === 'number' ? v : 0;
  };

  const presetNames = catalog?.presets.map(p => p.name) ?? ['Natural', 'Off'];
  const enabled = !!draft && draft.enabled;

  return (
    <div style={{ padding: '14px', borderBottom: '1px solid #1c202a', background: 'linear-gradient(180deg, #131720 0%, #11141b 100%)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Sparkles size={14} style={{ color: '#38bdf8' }} />
          <span style={{ fontSize: '11px', fontWeight: 700, color: '#f1f5f9', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            AI Skin Retouch
          </span>
        </div>
        {draft && (
          <button
            type="button"
            onClick={() => commit({ ...clone(draft), enabled: !draft.enabled })}
            title={enabled ? 'Turn skin retouch off for this photo' : 'Turn skin retouch on'}
            style={{ display: 'flex', alignItems: 'center', gap: '4px', background: 'transparent', border: '1px solid #232836', borderRadius: '4px', color: enabled ? '#38bdf8' : '#64748b', fontSize: '10px', padding: '2px 6px', cursor: 'pointer' }}
          >
            {enabled ? <Eye size={11} /> : <EyeOff size={11} />}
            <span>{enabled ? 'On' : 'Off'}</span>
          </button>
        )}
      </div>

      {/* Auto Edit retouch preset (used by Auto Edit for every photo) */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
        <span style={{ fontSize: '10px', color: '#94a3b8', whiteSpace: 'nowrap' }}>Auto Edit uses:</span>
        <select
          value={autoEditPreset}
          onChange={(e) => onSelectAutoEditPreset(e.target.value)}
          style={{ flex: 1, background: '#181b22', color: '#e2e8f0', border: '1px solid #232836', borderRadius: '4px', fontSize: '11px', padding: '3px 4px' }}
        >
          {presetNames.map(n => <option key={n} value={n}>{n}</option>)}
        </select>
      </div>

      {!draft ? (
        <div style={{ fontSize: '10.5px', color: '#94a3b8', lineHeight: 1.4 }}>
          Is photo par skin retouch nahi laga hai.
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            style={{ marginTop: '6px', width: '100%', justifyContent: 'center', display: 'flex', gap: '5px' }}
            onClick={() => applyPreset(autoEditPreset === 'Off' ? 'Natural' : autoEditPreset)}
          >
            <Wand2 size={11} /> Apply Skin Retouch ({autoEditPreset === 'Off' ? 'Natural' : autoEditPreset})
          </button>
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
            <span style={{ fontSize: '10px', color: '#94a3b8', whiteSpace: 'nowrap' }}>This photo:</span>
            <select
              value={presetNames.includes(draft.preset) ? draft.preset : ''}
              onChange={(e) => applyPreset(e.target.value)}
              style={{ flex: 1, background: '#181b22', color: '#e2e8f0', border: '1px solid #232836', borderRadius: '4px', fontSize: '11px', padding: '3px 4px' }}
            >
              {!presetNames.includes(draft.preset) && <option value="">{draft.preset || 'Custom'}</option>}
              {presetNames.map(n => <option key={n} value={n}>{n}</option>)}
            </select>
            <button
              type="button"
              title="Reset all retouch panels to this preset"
              onClick={() => applyPreset(presetNames.includes(draft.preset) ? draft.preset : 'Natural')}
              style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '2px', fontSize: '10px' }}
            >
              <RotateCcw size={11} /> All
            </button>
          </div>

          <div style={{ opacity: enabled ? 1 : 0.45, pointerEvents: enabled ? 'auto' : 'none' }}>
            {SECTIONS.map(sec => {
              const data = (draft as any)[sec.key] || {};
              const secOn = sec.toggle ? data.enabled !== false : true;
              const isOpen = !!open[sec.key];
              return (
                <div key={sec.key} style={{ borderTop: '1px dashed #232836', padding: '6px 0' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <button
                      type="button"
                      onClick={() => setOpen({ ...open, [sec.key]: !isOpen })}
                      style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '4px', background: 'transparent', border: 'none', color: '#e2e8f0', cursor: 'pointer', padding: 0, fontSize: '11px', fontWeight: 600, textAlign: 'left' }}
                    >
                      {isOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                      <span>{sec.title}</span>
                      <span style={{ fontSize: '9.5px', color: '#64748b', fontWeight: 400 }}>({sec.hindi})</span>
                    </button>
                    {sec.toggle && (
                      <button
                        type="button"
                        title={secOn ? 'Disable this panel' : 'Enable this panel'}
                        onClick={() => setValue(sec.key, 'enabled', !secOn, true)}
                        style={{ background: 'transparent', border: 'none', color: secOn ? '#38bdf8' : '#475569', cursor: 'pointer', padding: 0, display: 'flex' }}
                      >
                        {secOn ? <Eye size={12} /> : <EyeOff size={12} />}
                      </button>
                    )}
                    <button
                      type="button"
                      title="Reset this panel"
                      onClick={() => resetSection(sec.key)}
                      style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', padding: 0, display: 'flex' }}
                    >
                      <RotateCcw size={11} />
                    </button>
                  </div>

                  {isOpen && (
                    <div style={{ marginTop: '6px', opacity: secOn ? 1 : 0.45 }}>
                      {sec.key === 'skinMask' && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', marginBottom: '6px' }}>
                          {[
                            { k: 'excludeFeatures', label: 'Exclude eyes, brows, lips, nostrils' },
                            { k: 'restrictToBody', label: 'Limit mask to face & neck of each person' },
                          ].map(o => (
                            <label key={o.k} style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '10.5px', color: '#cbd5e1', cursor: 'pointer' }}>
                              <input type="checkbox" checked={data[o.k] !== false} onChange={(e) => setValue(sec.key, o.k, e.target.checked, true)} />
                              {o.label}
                            </label>
                          ))}
                        </div>
                      )}
                      {sec.key === 'heal' && (
                        <div style={{ display: 'flex', gap: '4px', marginBottom: '6px' }}>
                          {(['AUTO', 'SMALL', 'MEDIUM', 'LARGE'] as const).map(fs => (
                            <button
                              key={fs}
                              type="button"
                              onClick={() => commit({ ...clone(draft), heal: { ...draft.heal, faceSizePreset: fs } })}
                              style={{
                                flex: 1, padding: '2px 0', fontSize: '9.5px', borderRadius: '4px', cursor: 'pointer',
                                border: draft.heal.faceSizePreset === fs ? '1px solid #38bdf8' : '1px solid #232836',
                                background: draft.heal.faceSizePreset === fs ? 'rgba(56, 189, 248, 0.2)' : '#181b22',
                                color: draft.heal.faceSizePreset === fs ? '#38bdf8' : '#94a3b8',
                              }}
                            >
                              {fs === 'AUTO' ? 'Auto' : fs[0] + fs.slice(1).toLowerCase()}
                            </button>
                          ))}
                        </div>
                      )}
                      {sec.key === 'skinDetails' && (
                        <label style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '10.5px', color: '#cbd5e1', cursor: 'pointer', marginBottom: '4px' }}>
                          <input type="checkbox" checked={data.autoPortraitSize !== false} onChange={(e) => setValue(sec.key, 'autoPortraitSize', e.target.checked, true)} />
                          Auto Portrait Size (face se scale)
                        </label>
                      )}
                      {sec.key === 'skinTone' && (
                        <label style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '10.5px', color: '#cbd5e1', cursor: 'pointer', marginBottom: '4px' }}>
                          <input type="checkbox" checked={data.useSkinMask !== false} onChange={(e) => setValue(sec.key, 'useSkinMask', e.target.checked, true)} />
                          Use Skin Mask (sirf skin par)
                        </label>
                      )}
                      {sec.sliders.map(sl => {
                        if (sec.key === 'skinDetails' && sl.key === 'portraitSize' && data.autoPortraitSize !== false) return null;
                        const val = typeof data[sl.key] === 'number' ? data[sl.key] : 0;
                        return (
                          <div key={sl.key} className="slider-group" style={{ marginBottom: '6px' }}>
                            <div className="slider-header">
                              <span
                                onDoubleClick={() => setValue(sec.key, sl.key, defaultFor(sec.key, sl.key), true)}
                                title={`${sl.hint ? sl.hint + ' · ' : ''}Double-click to reset`}
                                style={{ cursor: 'default' }}
                              >
                                {sl.label}
                              </span>
                              <span className="slider-val">{sl.min < 0 && val > 0 ? `+${Math.round(val)}` : Math.round(val)}</span>
                            </div>
                            <input
                              type="range"
                              min={sl.min}
                              max={sl.max}
                              step={1}
                              value={val}
                              onChange={(e) => setValue(sec.key, sl.key, parseFloat(e.target.value), false)}
                              onPointerUp={(e) => setValue(sec.key, sl.key, parseFloat((e.target as HTMLInputElement).value), true)}
                              onKeyUp={(e) => setValue(sec.key, sl.key, parseFloat((e.target as HTMLInputElement).value), true)}
                              style={{ accentColor: '#38bdf8' }}
                            />
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          <div style={{ fontSize: '9.5px', color: '#64748b', marginTop: '4px', lineHeight: 1.35 }}>
            Sirf skin par lagta hai — aankhein, bhauhein, honth, baal, daadhi, bindi, jewellery aur kapde untouched rehte hain.
            Before/After view me "Mask" se dekh sakte hain kahan apply hua.
          </div>
        </>
      )}
    </div>
  );
};
