import React, { useState, useEffect, useCallback } from 'react';
import { Project, Photo, BatchJob, EditParameters, UserSelection, LicenseStatus } from './types';
import { api } from './api';
import { TopBar } from './components/TopBar';
import { Sidebar } from './components/Sidebar';
import { PhotoGrid } from './components/PhotoGrid';
import { BeforeAfterView } from './components/BeforeAfterView';
import { CompareView } from './components/CompareView';
import { InspectorPanel } from './components/InspectorPanel';
import { ImportModal } from './components/ImportModal';
import { ExportModal } from './components/ExportModal';
import { BatchLogsModal } from './components/BatchLogsModal';
import { ShortcutsModal } from './components/ShortcutsModal';
import { SettingsModal } from './components/SettingsModal';
import { PricingModal } from './components/PricingModal';
import { LightboxModal } from './components/LightboxModal';
import { AdminHubModal } from './components/AdminHubModal';
import { ShareProofingModal } from './components/ShareProofingModal';


export const App: React.FC = () => {
  // Projects State
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProject, setCurrentProject] = useState<Project | null>(null);

  // Photos State
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [selectedPhoto, setSelectedPhoto] = useState<Photo | null>(null);
  const [selectedPhotoIds, setSelectedPhotoIds] = useState<number[]>([]);

  // Filtering & View State
  const [currentCategory, setCurrentCategory] = useState<string>('ALL');
  const [selectedStar, setSelectedStar] = useState<number | undefined>(undefined);
  const [selectedScene, setSelectedScene] = useState<string>('ALL');
  const [sortBy, setSortBy] = useState<string>('ai_score_desc');
  const [thumbnailSize, setThumbnailSize] = useState<'small' | 'medium' | 'large'>('medium');
  const [viewMode, setViewMode] = useState<'grid' | 'before-after' | 'compare'>('grid');
  const [comparePhotos, setComparePhotos] = useState<Photo[]>([]);
  const [previewTimestamp, setPreviewTimestamp] = useState<number>(Date.now());

  // Lightbox Fullscreen State
  const [isLightboxOpen, setIsLightboxOpen] = useState<boolean>(false);
  const [lightboxIndex, setLightboxIndex] = useState<number>(0);

  // Batch Job State
  const [activeJob, setActiveJob] = useState<BatchJob | null>(null);

  // Modals
  const [isImportOpen, setIsImportOpen] = useState<boolean>(false);
  const [isExportOpen, setIsExportOpen] = useState<boolean>(false);
  const [isShareProofingOpen, setIsShareProofingOpen] = useState<boolean>(false);
  const [isLogsOpen, setIsLogsOpen] = useState<boolean>(false);
  const [isShortcutsOpen, setIsShortcutsOpen] = useState<boolean>(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [isPricingOpen, setIsPricingOpen] = useState<boolean>(false);
  const [isAdminHubOpen, setIsAdminHubOpen] = useState<boolean>(false);
  const [selectedStylePreset, setSelectedStylePreset] = useState<string>('Pure Light (No Color Tone)');

  // Spot Healing Brush State
  const [healBrushActive, setHealBrushActive] = useState<boolean>(false);
  const [healBrushRadius, setHealBrushRadius] = useState<number>(0.010);


  // License & Pricing State
  const [license, setLicense] = useState<LicenseStatus | null>(null);

  const loadLicense = async () => {
    try {
      const data = await api.getLicenseStatus();
      setLicense(data);
    } catch (err) {
      console.error('Error fetching license status:', err);
    }
  };

  // 1. Initial Load: Fetch Projects
  const loadProjects = async () => {
    loadLicense();
    try {
      const projs = await api.getProjects();
      setProjects(projs);
      if (projs.length > 0 && !currentProject) {
        // Load details for the most recent project
        loadProjectDetails(projs[0].id);
      }
    } catch (err) {
      console.error('Error fetching projects:', err);
    }
  };

  const loadProjectDetails = async (projectId: number) => {
    try {
      const proj = await api.getProject(projectId);
      setCurrentProject(proj);
      loadPhotos(projectId, currentCategory, selectedStar, selectedScene, sortBy);
    } catch (err) {
      console.error('Error loading project details:', err);
    }
  };

  const loadPhotos = async (
    projectId: number,
    cat = currentCategory,
    stars = selectedStar,
    scene = selectedScene,
    sort = sortBy
  ) => {
    try {
      const list = await api.getPhotos(projectId, cat, stars, scene, sort);
      setPhotos(list);
      if (list.length > 0) {
        if (!selectedPhoto || !list.find(p => p.id === selectedPhoto.id)) {
          setSelectedPhoto(list[0]);
        }
      } else {
        setSelectedPhoto(null);
      }
    } catch (err) {
      console.error('Error loading photos:', err);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  // 2. Poll Active Batch Job if running
  useEffect(() => {
    if (!activeJob || (activeJob.status !== 'RUNNING' && activeJob.status !== 'PAUSED')) {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const updated = await api.getJob(activeJob.id);
        setActiveJob(updated);
        if (updated.status === 'COMPLETED' || updated.status === 'FAILED' || updated.status === 'CANCELLED') {
          // Refresh current project counts and photos
          if (currentProject) {
            loadProjectDetails(currentProject.id);
            setPreviewTimestamp(Date.now());
          }
        }
      } catch (err) {
        console.error('Error polling job:', err);
      }
    }, 1200);

    return () => clearInterval(interval);
  }, [activeJob, currentProject]);

  // 3. Selection & Rating Handlers
  const handleUpdateSelection = async (photoId: number, selection: UserSelection) => {
    try {
      await api.updateSelection(photoId, selection);
      setPhotos(prev => prev.map(p => {
        if (p.id === photoId) {
          const effective = selection !== 'UNRATED' ? selection : p.ai_recommendation;
          return { ...p, user_selection: selection, effective_selection: effective };
        }
        return p;
      }));
      if (selectedPhoto?.id === photoId) {
        setSelectedPhoto(prev => {
          if (!prev) return null;
          const effective = selection !== 'UNRATED' ? selection : prev.ai_recommendation;
          return { ...prev, user_selection: selection, effective_selection: effective };
        });
      }
      if (currentProject) {
        api.getProject(currentProject.id).then(proj => setCurrentProject(proj));
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleUpdateRating = async (photoId: number, rating: number) => {
    try {
      await api.updateRating(photoId, rating);
      setPhotos(prev => prev.map(p => p.id === photoId ? { ...p, star_rating: rating } : p));
      if (selectedPhoto?.id === photoId) {
        setSelectedPhoto(prev => prev ? { ...prev, star_rating: rating } : null);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleUpdateEdits = async (photoId: number, params: EditParameters) => {
    try {
      await api.updateEdits(photoId, params);
      setPhotos(prev => prev.map(p => p.id === photoId ? { ...p, edit_params: params, is_edited: 1, manual_override: 1 } : p));
      if (selectedPhoto?.id === photoId) {
        setSelectedPhoto(prev => prev ? { ...prev, edit_params: params, is_edited: 1, manual_override: 1 } : null);
      }
      setPreviewTimestamp(Date.now());
    } catch (err) {
      console.error(err);
    }
  };

  const handleResetEdits = async (photoId: number) => {
    try {
      await api.resetEdits(photoId);
      const updated = await api.getPhoto(photoId);
      setPhotos(prev => prev.map(p => p.id === photoId ? updated : p));
      if (selectedPhoto?.id === photoId) {
        setSelectedPhoto(updated);
      }
      setPreviewTimestamp(Date.now());
    } catch (err) {
      console.error(err);
    }
  };

  const handleAutoEditSingle = async (photoId: number, presetName = 'Natural Wedding') => {
    try {
      const res = await api.autoEditSingle(photoId, presetName);
      setPhotos(prev => prev.map(p => p.id === photoId ? { ...p, edit_params: res.edit_params, is_edited: 1 } : p));
      if (selectedPhoto?.id === photoId) {
        setSelectedPhoto(prev => prev ? { ...prev, edit_params: res.edit_params, is_edited: 1 } : null);
      }
      setPreviewTimestamp(Date.now());
    } catch (err) {
      console.error(err);
    }
  };

  // 4. Batch Triggers
  const handleStartCull = async () => {
    if (!currentProject) return;
    try {
      const { job_id } = await api.startCulling(currentProject.id);
      const job = await api.getJob(job_id);
      setActiveJob(job);
    } catch (err: any) {
      alert(`Could not start AI Culling: ${err.message}`);
    }
  };

  const handleStartAutoEdit = async () => {
    if (!currentProject) return;
    try {
      const targetIds = selectedPhotoIds.length > 0 ? selectedPhotoIds : undefined;
      const { job_id } = await api.startAutoEdit(currentProject.id, selectedStylePreset, targetIds);
      const job = await api.getJob(job_id);
      setActiveJob(job);
    } catch (err: any) {
      alert(`Could not start Auto Edit: ${err.message}`);
    }
  };


  const handleStartExport = async (options: any): Promise<string | void> => {
    if (!currentProject) return;
    try {
      const { job_id } = await api.startExport(currentProject.id, options);
      const job = await api.getJob(job_id);
      setActiveJob(job);
      return job_id;
    } catch (err: any) {
      alert(`Could not start Export: ${err.message}`);
      throw err;
    }
  };

  // 5. Delete Handlers
  const handleDeletePhotos = async (photoIds: number[]) => {
    if (photoIds.length === 0) return;
    const count = photoIds.length;
    const confirmMsg = count === 1
      ? 'Kya aap is photo ko project se hatana chahte hain? (Aapke computer se original photo delete nahi hogi)'
      : `Kya aap in ${count} photos ko project se hatana chahte hain? (Aapke computer se original photos safe rahengi)`;

    if (!window.confirm(confirmMsg)) return;

    try {
      await api.deletePhotosBatch(photoIds);
      setSelectedPhotoIds(prev => prev.filter(id => !photoIds.includes(id)));
      if (selectedPhoto && photoIds.includes(selectedPhoto.id)) {
        setSelectedPhoto(null);
      }
      if (currentProject) {
        await loadProjectDetails(currentProject.id);
      }
    } catch (err: any) {
      alert(`Photo hatane me error: ${err.message}`);
    }
  };

  const handleDeleteProject = async (projectId: number) => {
    const proj = projects.find(p => p.id === projectId);
    const confirmMsg = `Kya aap project "${proj?.name || 'Wedding'}" ko Ai PhotoFlow se hatana chahte hain?\n(Aapke computer me stored photos 100% safe rahenge)`;

    if (!window.confirm(confirmMsg)) return;

    try {
      await api.deleteProject(projectId);
      const remaining = projects.filter(p => p.id !== projectId);
      setProjects(remaining);
      if (remaining.length > 0) {
        await loadProjectDetails(remaining[0].id);
      } else {
        setCurrentProject(null);
        setPhotos([]);
        setSelectedPhoto(null);
      }
    } catch (err: any) {
      alert(`Project delete karne me error: ${err.message}`);
    }
  };

  // 6. Global Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger shortcuts when typing in input
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes((e.target as HTMLElement).tagName)) {
        return;
      }

      // Secret Admin Hub Shortcut for Owner (Anil Sharma):
      // Completely hidden from normal users.
      // Accessible via: Cmd + Shift + A (or Ctrl + Shift + A) or Cmd + Option + A or F12
      const isCmdOrCtrl = e.metaKey || e.ctrlKey;
      const k = e.key ? e.key.toLowerCase() : '';
      const isA = k === 'a' || e.code === 'KeyA';

      if ((isCmdOrCtrl && (e.shiftKey || e.altKey) && isA) || e.key === 'F12') {
        e.preventDefault();
        setIsAdminHubOpen(true);
        return;
      }

      if (e.key === 'F10' || (isCmdOrCtrl && e.altKey && (k === 's' || e.code === 'KeyS'))) {
        e.preventDefault();
        setIsSettingsOpen(true);
        return;
      }

      // Cmd+A / Ctrl+A: Select All photos in current view
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'a') {
        e.preventDefault();
        setSelectedPhotoIds(photos.map(p => p.id));
        return;
      }

      // Delete / Backspace: Remove selected photo(s)
      if (e.key === 'Backspace' || e.key === 'Delete') {
        const toDelete = selectedPhotoIds.length > 0 ? selectedPhotoIds : (selectedPhoto ? [selectedPhoto.id] : []);
        if (toDelete.length > 0) {
          e.preventDefault();
          handleDeletePhotos(toDelete);
          return;
        }
      }

      if (!selectedPhoto) return;

      const key = e.key.toUpperCase();

      if (key === 'B') {
        e.preventDefault();
        handleUpdateSelection(selectedPhoto.id, 'BEST');
      } else if (key === 'P') {
        e.preventDefault();
        handleUpdateSelection(selectedPhoto.id, 'SELECTED');
      } else if (key === 'R') {
        e.preventDefault();
        handleUpdateSelection(selectedPhoto.id, 'REVIEW');
      } else if (key === 'X') {
        e.preventDefault();
        handleUpdateSelection(selectedPhoto.id, 'REJECT');
      } else if (key === 'U') {
        e.preventDefault();
        handleUpdateSelection(selectedPhoto.id, 'UNRATED');
      } else if (['1', '2', '3', '4', '5'].includes(key)) {
        e.preventDefault();
        handleUpdateRating(selectedPhoto.id, parseInt(key));
      } else if (key === '0') {
        e.preventDefault();
        handleUpdateRating(selectedPhoto.id, 0);
      } else if (e.code === 'Space') {
        e.preventDefault();
        setViewMode(prev => prev === 'before-after' ? 'grid' : 'before-after');
      } else if (key === 'C') {
        e.preventDefault();
        if (selectedPhoto.duplicate_group_id && currentProject) {
          api.getDuplicateGroupPhotos(currentProject.id, selectedPhoto.duplicate_group_id).then(grp => {
            if (grp.length > 1) {
              setComparePhotos(grp);
              setViewMode('compare');
            }
          }).catch(() => {
            const group = photos.filter(p => p.duplicate_group_id === selectedPhoto.duplicate_group_id);
            if (group.length > 1) {
              setComparePhotos(group);
              setViewMode('compare');
            }
          });
        }
      } else if (key === 'E') {
        e.preventDefault();
        handleAutoEditSingle(selectedPhoto.id);
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        const currIdx = photos.findIndex(p => p.id === selectedPhoto.id);
        if (currIdx < photos.length - 1) {
          setSelectedPhoto(photos[currIdx + 1]);
        }
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        const currIdx = photos.findIndex(p => p.id === selectedPhoto.id);
        if (currIdx > 0) {
          setSelectedPhoto(photos[currIdx - 1]);
        }
      } else if (e.key === 'Escape') {
        if (viewMode !== 'grid') {
          setViewMode('grid');
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedPhoto, photos, selectedPhotoIds, viewMode]);

  return (
    <div className="app-container">
      {/* Top Bar */}
      <TopBar
        currentProject={currentProject}
        projects={projects}
        license={license}
        onOpenPricing={() => setIsPricingOpen(true)}
        onSelectProject={(id) => loadProjectDetails(id)}
        onOpenImport={() => setIsImportOpen(true)}
        onOpenExport={() => setIsExportOpen(true)}
        onOpenShareProofing={() => setIsShareProofingOpen(true)}
        onOpenLogs={() => setIsLogsOpen(true)}
        onOpenShortcuts={() => setIsShortcutsOpen(true)}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenAdminHub={() => setIsAdminHubOpen(true)}
        onStartCull={handleStartCull}
        onStartAutoEdit={handleStartAutoEdit}
        onDeleteProject={handleDeleteProject}
        activeJob={activeJob}
        onPauseJob={() => activeJob && api.pauseJob(activeJob.id)}
        onResumeJob={() => activeJob && api.resumeJob(activeJob.id)}
        onCancelJob={() => activeJob && api.cancelJob(activeJob.id)}
      />

      {/* Main Workspace Layout */}
      <div className="workspace-layout">
        {/* Left Sidebar */}
        <Sidebar
          currentCategory={currentCategory}
          onSelectCategory={(cat) => {
            setCurrentCategory(cat);
            if (currentProject) loadPhotos(currentProject.id, cat, selectedStar, selectedScene, sortBy);
          }}
          selectedStar={selectedStar}
          onSelectStar={(stars) => {
            setSelectedStar(stars);
            if (currentProject) loadPhotos(currentProject.id, currentCategory, stars, selectedScene, sortBy);
          }}
          selectedScene={selectedScene}
          onSelectScene={(scene) => {
            setSelectedScene(scene);
            if (currentProject) loadPhotos(currentProject.id, currentCategory, selectedStar, scene, sortBy);
          }}
          counts={currentProject?.counts}
        />

        {/* Center Main View */}
        <main className="main-content">
          {viewMode === 'grid' ? (
            <PhotoGrid
              photos={photos}
              selectedPhoto={selectedPhoto}
              onSelectPhoto={(p) => setSelectedPhoto(p)}
              selectedPhotoIds={selectedPhotoIds}
              onToggleSelectPhotoId={(id) => {
                setSelectedPhotoIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
              }}
              onSelectAll={() => setSelectedPhotoIds(photos.map(p => p.id))}
              onClearSelection={() => setSelectedPhotoIds([])}
              onUpdatePhotoSelection={handleUpdateSelection}
              onUpdatePhotoRating={handleUpdateRating}
              onOpenCompare={(group) => {
                setComparePhotos(group);
                setViewMode('compare');
              }}
              onOpenLightbox={(idx) => {
                setLightboxIndex(idx);
                setIsLightboxOpen(true);
              }}
              onDeletePhotos={handleDeletePhotos}
              onAutoEditSelected={handleStartAutoEdit}
              previewTimestamp={previewTimestamp}
              thumbnailSize={thumbnailSize}
              onChangeThumbnailSize={setThumbnailSize}
              sortBy={sortBy}
              onChangeSortBy={(sort) => {
                setSortBy(sort);
                if (currentProject) loadPhotos(currentProject.id, currentCategory, selectedStar, selectedScene, sort);
              }}
              currentCategory={currentCategory}
              projectId={currentProject?.id}
            />
          ) : viewMode === 'before-after' && selectedPhoto ? (
            <BeforeAfterView
              photo={selectedPhoto}
              previewTimestamp={previewTimestamp}
              onResetEdits={handleResetEdits}
              onAutoEditSingle={handleAutoEditSingle}
              onUpdateEdits={handleUpdateEdits}
              healBrushActive={healBrushActive}
              onToggleHealBrush={setHealBrushActive}
              healBrushRadius={healBrushRadius}
              onChangeHealBrushRadius={setHealBrushRadius}
            />
          ) : viewMode === 'compare' ? (
            <CompareView
              groupPhotos={comparePhotos}
              onBackToGrid={() => setViewMode('grid')}
              onUpdatePhotoSelection={handleUpdateSelection}
              onUpdatePhotoRating={handleUpdateRating}
            />
          ) : null}
        </main>

        {/* Right Inspector Panel */}
        <InspectorPanel
          photo={selectedPhoto}
          selectedStylePreset={selectedStylePreset}
          onSelectStylePreset={setSelectedStylePreset}
          onUpdateEdits={handleUpdateEdits}
          onResetEdits={handleResetEdits}
          onAutoEditSingle={handleAutoEditSingle}
          onUpdateSelection={handleUpdateSelection}
          healBrushActive={healBrushActive}
          onToggleHealBrush={(active) => {
            setHealBrushActive(active);
            if (active && viewMode === 'grid') {
              setViewMode('before-after');
            }
          }}
          healBrushRadius={healBrushRadius}
          onChangeHealBrushRadius={setHealBrushRadius}
        />
      </div>

      {/* Modals */}
      <ImportModal
        isOpen={isImportOpen}
        onClose={() => setIsImportOpen(false)}
        onImport={async (folderPath, projName) => {
          const res = await api.importFolder(folderPath, projName);
          await loadProjects();
          await loadProjectDetails(res.project_id);
        }}
      />

      <ExportModal
        isOpen={isExportOpen}
        onClose={() => setIsExportOpen(false)}
        defaultFolder={currentProject?.folder_path || ''}
        projectId={currentProject?.id}
        clientSelectedCount={currentProject?.counts?.client_selected_count || 0}
        onStartExport={handleStartExport}
      />

      <ShareProofingModal
        isOpen={isShareProofingOpen}
        onClose={() => setIsShareProofingOpen(false)}
        project={currentProject}
        photos={photos}
        onRefreshProject={() => {
          if (currentProject) {
            loadProjectDetails(currentProject.id);
          }
        }}
      />

      <BatchLogsModal
        isOpen={isLogsOpen}
        onClose={() => setIsLogsOpen(false)}
        activeJob={activeJob}
      />

      <ShortcutsModal
        isOpen={isShortcutsOpen}
        onClose={() => setIsShortcutsOpen(false)}
      />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />

      <AdminHubModal
        isOpen={isAdminHubOpen}
        onClose={() => setIsAdminHubOpen(false)}
      />

      <PricingModal
        isOpen={isPricingOpen}
        onClose={() => setIsPricingOpen(false)}
        onLicenseUpdated={(lic) => setLicense(lic)}
        onOpenAdminSettings={() => setIsAdminHubOpen(true)}
      />

      <LightboxModal
        isOpen={isLightboxOpen}
        photos={photos}
        currentIndex={lightboxIndex}
        previewTimestamp={previewTimestamp}
        onClose={() => setIsLightboxOpen(false)}
        onNavigate={(newIdx) => {
          setLightboxIndex(newIdx);
          if (photos[newIdx]) {
            setSelectedPhoto(photos[newIdx]);
          }
        }}
        onUpdateSelection={handleUpdateSelection}
        onUpdateRating={handleUpdateRating}
        onUpdateEdits={handleUpdateEdits}
      />
    </div>
  );

};

export default App;
