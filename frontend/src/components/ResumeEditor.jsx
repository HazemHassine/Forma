import { useState, useRef, useEffect } from 'react';
import {
  User,
  MessageSquare,
  GraduationCap,
  Briefcase,
  Rocket,
  Microscope,
  Zap,
  Award,
  Globe,
  ClipboardList,
  X,
  ChevronDown,
  ChevronUp,
  Plus,
  Trash2,
  GripVertical,
  RotateCcw,
} from 'lucide-react';
import { photoApi } from '../api';
import { useToast } from '../App';
import AISuggest from './AISuggest';
import {
  LANGUAGE_LEVELS,
  DEFAULT_SECTION_ORDER,
  SECTION_DEFINITIONS,
} from '../constants/resumeSections';
import './ResumeEditor.css';

const SECTION_ICONS = {
  about_me: <MessageSquare size={15} />,
  work_experience: <Briefcase size={15} />,
  education: <GraduationCap size={15} />,
  projects: <Rocket size={15} />,
  research: <Microscope size={15} />,
  skills: <Zap size={15} />,
  certificates: <Award size={15} />,
  languages: <Globe size={15} />,
  references: <ClipboardList size={15} />,
};

const SECTION_METADATA = SECTION_DEFINITIONS.reduce((acc, def) => {
  acc[def.id] = {
    ...def,
    icon: SECTION_ICONS[def.id] || null,
  };
  return acc;
}, {});

const STANDARD_PERSONAL_FIELDS = [
  { key: 'title', label: 'Professional Title', placeholder: 'Software Engineer', isFull: false },
  { key: 'email', label: 'Email', placeholder: 'john@example.com', type: 'email', isFull: false },
  { key: 'phone', label: 'Phone', placeholder: '+1 234 567 890', isFull: false },
  { key: 'website', label: 'Website', placeholder: 'yourwebsite.com or https://...', isFull: false },
  { key: 'address', label: 'Address', placeholder: 'City, Country', isFull: true },
  { key: 'github', label: 'GitHub', placeholder: 'github.com/username', isFull: false },
  { key: 'linkedin', label: 'LinkedIn', placeholder: 'linkedin.com/in/username', isFull: false },
  { key: 'photo_path', label: 'Profile Photo', isFull: true, isPhoto: true },
];

function Section({
  title,
  icon,
  children,
  defaultOpen = false,
  actions,
  draggable = false,
  isDragging = false,
  isDragOver = false,
  onDragStart,
  onDragOver,
  onDragEnter,
  onDragLeave,
  onDrop,
  onDragEnd,
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div
      className={`editor-section ${isDragging ? 'is-dragging' : ''} ${isDragOver ? 'drag-over' : ''}`}
      onDragOver={onDragOver}
      onDragEnter={onDragEnter}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      <div className="editor-section-header" onClick={() => setOpen(!open)}>
        <div className="editor-section-header-left">
          {draggable && (
            <span
              className="editor-drag-handle"
              title="Drag to reorder section"
              draggable
              onDragStart={onDragStart}
              onDragEnd={onDragEnd}
              onClick={e => e.stopPropagation()}
            >
              <GripVertical size={15} />
            </span>
          )}
          <span className="editor-section-icon">{icon}</span>
          <span className="editor-section-title">{title}</span>
        </div>
        <div className="editor-section-header-actions" onClick={e => e.stopPropagation()}>
          {actions}
        </div>
        <span className={`editor-section-chevron ${open ? 'open' : ''}`}><ChevronDown size={14} /></span>
      </div>
      <div
        className={`editor-section-body ${open ? 'expanded' : 'collapsed'}`}
      >
        <div className="editor-section-content">
          {children}
        </div>
      </div>
    </div>
  );
}

export default function ResumeEditor({ data, onChange }) {
  const addToast = useToast();
  const fileInputRef = useRef(null);
  const addSectionContainerRef = useRef(null);
  const personalAddContainerRef = useRef(null);

  const [draggedIndex, setDraggedIndex] = useState(null);
  const [dragOverIndex, setDragOverIndex] = useState(null);
  const [addSectionOpen, setAddSectionOpen] = useState(false);
  const [personalAddOpen, setPersonalAddOpen] = useState(false);

  // Close dropdowns on outside click
  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (addSectionContainerRef.current && !addSectionContainerRef.current.contains(e.target)) {
        setAddSectionOpen(false);
      }
      if (personalAddContainerRef.current && !personalAddContainerRef.current.contains(e.target)) {
        setPersonalAddOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  if (!data) return null;

  const currentSectionOrder = Array.isArray(data.section_order)
    ? data.section_order.filter(id => id in SECTION_METADATA)
    : DEFAULT_SECTION_ORDER;

  const availableSections = DEFAULT_SECTION_ORDER
    .filter(id => !currentSectionOrder.includes(id))
    .map(id => SECTION_METADATA[id]);

  const isDefaultOrder =
    currentSectionOrder.length === DEFAULT_SECTION_ORDER.length &&
    currentSectionOrder.every((val, idx) => val === DEFAULT_SECTION_ORDER[idx]);

  const update = (path, value) => {
    const newData = JSON.parse(JSON.stringify(data));
    const keys = path.split('.');
    let obj = newData;
    for (let i = 0; i < keys.length - 1; i++) {
      const key = isNaN(keys[i]) ? keys[i] : parseInt(keys[i]);
      obj = obj[key];
    }
    const lastKey = isNaN(keys[keys.length - 1]) ? keys[keys.length - 1] : parseInt(keys[keys.length - 1]);
    obj[lastKey] = value;
    onChange(newData);
  };

  const addListItem = (path, template) => {
    const newData = JSON.parse(JSON.stringify(data));
    const keys = path.split('.');
    let obj = newData;
    for (const key of keys) {
      obj = obj[isNaN(key) ? key : parseInt(key)];
    }
    obj.push(template);
    onChange(newData);
  };

  const removeListItem = (path, index) => {
    const newData = JSON.parse(JSON.stringify(data));
    const keys = path.split('.');
    let obj = newData;
    for (const key of keys) {
      obj = obj[isNaN(key) ? key : parseInt(key)];
    }
    obj.splice(index, 1);
    onChange(newData);
  };

  const handlePhotoUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      const result = await photoApi.upload(file);
      update('personal_info.photo_path', result.photo_path || result.path || file.name);
      addToast('Photo uploaded successfully', 'success');
    } catch (err) {
      addToast(err.message || 'Failed to upload photo', 'error');
    }
  };

  const moveSection = (fromIndex, delta) => {
    const targetIndex = fromIndex + delta;
    if (targetIndex < 0 || targetIndex >= currentSectionOrder.length) return;
    const nextOrder = [...currentSectionOrder];
    const [moved] = nextOrder.splice(fromIndex, 1);
    nextOrder.splice(targetIndex, 0, moved);
    onChange({ ...data, section_order: nextOrder });
  };

  const removeSection = (sectionId) => {
    const nextOrder = currentSectionOrder.filter(id => id !== sectionId);
    onChange({ ...data, section_order: nextOrder });
    addToast(`Removed ${SECTION_METADATA[sectionId]?.title || 'section'}. You can restore it anytime with "+ Add Section".`, 'info');
  };

  const addSection = (sectionId) => {
    if (currentSectionOrder.includes(sectionId)) return;
    const nextOrder = [...currentSectionOrder, sectionId];
    onChange({ ...data, section_order: nextOrder });
    addToast(`Added ${SECTION_METADATA[sectionId]?.title || 'section'}`, 'success');
  };

  const resetSectionOrder = () => {
    onChange({ ...data, section_order: DEFAULT_SECTION_ORDER });
    addToast('Reset to default section order', 'info');
  };

  // Drag & drop handlers
  const handleDragStart = (e, index) => {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', String(index));
  };

  const handleDragOver = (e, index) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    if (dragOverIndex !== index) {
      setDragOverIndex(index);
    }
  };

  const handleDragLeave = (e) => {
    if (e.currentTarget.contains(e.relatedTarget)) return;
    setDragOverIndex(null);
  };

  const handleDrop = (e, targetIndex) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === targetIndex) {
      setDraggedIndex(null);
      setDragOverIndex(null);
      return;
    }
    const nextOrder = [...currentSectionOrder];
    const [moved] = nextOrder.splice(draggedIndex, 1);
    nextOrder.splice(targetIndex, 0, moved);
    setDraggedIndex(null);
    setDragOverIndex(null);
    onChange({ ...data, section_order: nextOrder });
    addToast('Section order updated', 'info');
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
    setDragOverIndex(null);
  };

  const pi = data.personal_info || {};
  const education = data.education || [];
  const experience = data.work_experience || [];
  const projects = data.projects || [];
  const research = data.research || [];
  const skills = data.skills || [];
  const certificates = data.certificates || [];
  const languages = data.languages || [];

  const isPersonalFieldActive = (field) => {
    if (field.isPhoto) {
      return Boolean(pi.photo_path);
    }
    return pi[field.key] !== undefined && pi[field.key] !== null;
  };

  const availablePersonalFields = STANDARD_PERSONAL_FIELDS.filter(
    f => !isPersonalFieldActive(f)
  );

  const removePersonalField = (key) => {
    const newData = JSON.parse(JSON.stringify(data));
    if (newData.personal_info) {
      delete newData.personal_info[key];
      if (key === 'photo_path') newData.personal_info.photo_path = null;
    }
    onChange(newData);
    const fieldDef = STANDARD_PERSONAL_FIELDS.find(f => f.key === key);
    addToast(`Removed ${fieldDef?.label || key}`, 'info');
  };

  const addPersonalField = (key) => {
    const newData = JSON.parse(JSON.stringify(data));
    if (!newData.personal_info) newData.personal_info = {};
    newData.personal_info[key] = '';
    onChange(newData);
    const fieldDef = STANDARD_PERSONAL_FIELDS.find(f => f.key === key);
    addToast(`Added ${fieldDef?.label || key}`, 'success');
  };

  const addCustomContactField = () => {
    const newData = JSON.parse(JSON.stringify(data));
    if (!newData.personal_info) newData.personal_info = {};
    if (!Array.isArray(newData.personal_info.custom_fields)) {
      newData.personal_info.custom_fields = [];
    }
    newData.personal_info.custom_fields.push({
      label: 'Portfolio',
      value: '',
      url: '',
    });
    onChange(newData);
    addToast('Added custom field', 'success');
  };

  const removeCustomContactField = (index) => {
    const newData = JSON.parse(JSON.stringify(data));
    if (Array.isArray(newData.personal_info?.custom_fields)) {
      newData.personal_info.custom_fields.splice(index, 1);
    }
    onChange(newData);
  };

  const renderSectionContent = (sectionId) => {
    switch (sectionId) {
      case 'about_me':
        return (
          <div className="textarea-with-ai">
            <textarea
              value={data.about_me || ''}
              onChange={e => update('about_me', e.target.value)}
              placeholder="Write a brief professional summary..."
              rows={4}
            />
          </div>
        );

      case 'education':
        return (
          <>
            {education.map((edu, i) => (
              <div className="list-item-card" key={i}>
                <div className="list-item-header">
                  <span className="list-item-number">#{i + 1}</span>
                  <button className="list-item-remove" onClick={() => removeListItem('education', i)}><X size={12} /> Remove</button>
                </div>
                <div className="editor-grid">
                  <div className="field-group">
                    <label className="field-label">Institution</label>
                    <input value={edu.institution || ''} onChange={e => update(`education.${i}.institution`, e.target.value)} placeholder="University name" />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Location</label>
                    <input value={edu.location || ''} onChange={e => update(`education.${i}.location`, e.target.value)} placeholder="City, Country" />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Degree</label>
                    <input value={edu.degree || ''} onChange={e => update(`education.${i}.degree`, e.target.value)} placeholder="B.Sc. Computer Science" />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Dates</label>
                    <input value={edu.dates || ''} onChange={e => update(`education.${i}.dates`, e.target.value)} placeholder="2018 - 2022" />
                  </div>
                  <div className="field-group editor-full">
                    <label className="field-label">Details</label>
                    <textarea value={edu.details || ''} onChange={e => update(`education.${i}.details`, e.target.value)} placeholder="Relevant coursework, GPA, honors..." rows={2} />
                  </div>
                </div>
              </div>
            ))}
            <button className="add-item-btn" onClick={() => addListItem('education', { institution: '', location: '', degree: '', dates: '', details: '' })}>
              <Plus size={14} /> Add Education
            </button>
          </>
        );

      case 'work_experience':
        return (
          <>
            {experience.map((exp, i) => (
              <div className="list-item-card" key={i}>
                <div className="list-item-header">
                  <span className="list-item-number">#{i + 1}</span>
                  <button className="list-item-remove" onClick={() => removeListItem('work_experience', i)}><X size={12} /> Remove</button>
                </div>
                <div className="editor-grid">
                  <div className="field-group">
                    <label className="field-label">Company</label>
                    <input value={exp.company || ''} onChange={e => update(`work_experience.${i}.company`, e.target.value)} placeholder="Company name" />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Location</label>
                    <input value={exp.location || ''} onChange={e => update(`work_experience.${i}.location`, e.target.value)} placeholder="City, Country" />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Role</label>
                    <input value={exp.role || ''} onChange={e => update(`work_experience.${i}.role`, e.target.value)} placeholder="Software Engineer" />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Dates</label>
                    <input value={exp.dates || ''} onChange={e => update(`work_experience.${i}.dates`, e.target.value)} placeholder="Jan 2022 - Present" />
                  </div>
                </div>
                <div className="field-group" style={{ marginTop: 12 }}>
                  <label className="field-label">Bullet Points</label>
                  <div className="bullet-list">
                    {(exp.bullets || []).map((bullet, j) => (
                      <div className="bullet-item" key={j}>
                        <span className="bullet-marker">•</span>
                        <input
                          value={bullet}
                          onChange={e => {
                            const newBullets = [...(exp.bullets || [])];
                            newBullets[j] = e.target.value;
                            update(`work_experience.${i}.bullets`, newBullets);
                          }}
                          placeholder="Describe an achievement..."
                        />
                        <AISuggest
                          sectionType="work_experience_bullet"
                          currentContent={bullet}
                          onAccept={val => {
                            const newBullets = [...(exp.bullets || [])];
                            newBullets[j] = val;
                            update(`work_experience.${i}.bullets`, newBullets);
                          }}
                        />
                        <button className="list-item-remove" onClick={() => {
                          const newBullets = [...(exp.bullets || [])];
                          newBullets.splice(j, 1);
                          update(`work_experience.${i}.bullets`, newBullets);
                        }}><X size={12} /></button>
                      </div>
                    ))}
                  </div>
                  <button className="add-item-btn" style={{ marginTop: 6 }} onClick={() => {
                    const newBullets = [...(exp.bullets || []), ''];
                    update(`work_experience.${i}.bullets`, newBullets);
                  }}><Plus size={14} /> Add Bullet</button>
                </div>
              </div>
            ))}
            <button className="add-item-btn" onClick={() => addListItem('work_experience', { company: '', location: '', role: '', dates: '', bullets: [''] })}>
              <Plus size={14} /> Add Experience
            </button>
          </>
        );

      case 'projects':
        return (
          <>
            {projects.map((proj, i) => (
              <div className="list-item-card" key={i}>
                <div className="list-item-header">
                  <span className="list-item-number">#{i + 1}</span>
                  <button className="list-item-remove" onClick={() => removeListItem('projects', i)}><X size={12} /> Remove</button>
                </div>
                <div className="editor-grid">
                  <div className="field-group">
                    <label className="field-label">Project Name</label>
                    <input value={proj.name || ''} onChange={e => update(`projects.${i}.name`, e.target.value)} placeholder="Project name" />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Type</label>
                    <input value={proj.type || ''} onChange={e => update(`projects.${i}.type`, e.target.value)} placeholder="Personal / Academic / Open Source" />
                  </div>
                  <div className="field-group editor-full">
                    <label className="field-label">Description</label>
                    <textarea value={proj.description || ''} onChange={e => update(`projects.${i}.description`, e.target.value)} placeholder="What does this project do?" rows={2} />
                  </div>
                  <div className="field-group editor-full">
                    <label className="field-label">Tech Stack</label>
                    <input value={proj.stack || ''} onChange={e => update(`projects.${i}.stack`, e.target.value)} placeholder="React, Node.js, PostgreSQL" />
                  </div>
                </div>
                <div className="field-group" style={{ marginTop: 12 }}>
                  <label className="field-label">Bullet Points</label>
                  <div className="bullet-list">
                    {(proj.bullets || []).map((bullet, j) => (
                      <div className="bullet-item" key={j}>
                        <span className="bullet-marker">•</span>
                        <input
                          value={bullet}
                          onChange={e => {
                            const newBullets = [...(proj.bullets || [])];
                            newBullets[j] = e.target.value;
                            update(`projects.${i}.bullets`, newBullets);
                          }}
                          placeholder="Describe a feature or outcome..."
                        />
                        <button className="list-item-remove" onClick={() => {
                          const newBullets = [...(proj.bullets || [])];
                          newBullets.splice(j, 1);
                          update(`projects.${i}.bullets`, newBullets);
                        }}><X size={12} /></button>
                      </div>
                    ))}
                  </div>
                  <button className="add-item-btn" style={{ marginTop: 6 }} onClick={() => {
                    const newBullets = [...(proj.bullets || []), ''];
                    update(`projects.${i}.bullets`, newBullets);
                  }}><Plus size={14} /> Add Bullet</button>
                </div>
              </div>
            ))}
            <button className="add-item-btn" onClick={() => addListItem('projects', { name: '', type: '', description: '', stack: '', bullets: [''] })}>
              <Plus size={14} /> Add Project
            </button>
          </>
        );

      case 'research':
        return (
          <>
            {research.map((res, i) => (
              <div className="list-item-card" key={i}>
                <div className="list-item-header">
                  <span className="list-item-number">#{i + 1}</span>
                  <button className="list-item-remove" onClick={() => removeListItem('research', i)}><X size={12} /> Remove</button>
                </div>
                <div className="editor-grid">
                  <div className="field-group">
                    <label className="field-label">Title</label>
                    <input value={res.title || ''} onChange={e => update(`research.${i}.title`, e.target.value)} placeholder="Research title" />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Institution</label>
                    <input value={res.institution || ''} onChange={e => update(`research.${i}.institution`, e.target.value)} placeholder="Research institution" />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Date</label>
                    <input value={res.date || ''} onChange={e => update(`research.${i}.date`, e.target.value)} placeholder="2023" />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Focus Area</label>
                    <input value={res.focus || ''} onChange={e => update(`research.${i}.focus`, e.target.value)} placeholder="Machine Learning, NLP..." />
                  </div>
                  <div className="field-group editor-full">
                    <label className="field-label">Description</label>
                    <textarea value={res.description || ''} onChange={e => update(`research.${i}.description`, e.target.value)} placeholder="Describe the research..." rows={2} />
                  </div>
                </div>
              </div>
            ))}
            <button className="add-item-btn" onClick={() => addListItem('research', { title: '', institution: '', date: '', description: '', focus: '' })}>
              <Plus size={14} /> Add Research
            </button>
          </>
        );

      case 'skills':
        return (
          <SkillsEditor skills={skills} onChange={newSkills => {
            const newData = { ...data, skills: newSkills };
            onChange(newData);
          }} />
        );

      case 'certificates':
        return (
          <>
            {certificates.map((cert, i) => (
              <div className="list-item-card" key={i}>
                <div className="list-item-header">
                  <span className="list-item-number">#{i + 1}</span>
                  <button className="list-item-remove" onClick={() => removeListItem('certificates', i)}><X size={12} /> Remove</button>
                </div>
                <div className="editor-grid">
                  <div className="field-group">
                    <label className="field-label">Certificate Name</label>
                    <input value={cert.name || ''} onChange={e => update(`certificates.${i}.name`, e.target.value)} placeholder="AWS Solutions Architect" />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Issuer</label>
                    <input value={cert.issuer || ''} onChange={e => update(`certificates.${i}.issuer`, e.target.value)} placeholder="Amazon Web Services" />
                  </div>
                </div>
              </div>
            ))}
            <button className="add-item-btn" onClick={() => addListItem('certificates', { name: '', issuer: '' })}>
              <Plus size={14} /> Add Certificate
            </button>
          </>
        );

      case 'languages':
        return (
          <>
            {languages.map((lang, i) => (
              <div className="list-item-card" key={i}>
                <div className="list-item-header">
                  <span className="list-item-number">#{i + 1}</span>
                  <button className="list-item-remove" onClick={() => removeListItem('languages', i)}><X size={12} /> Remove</button>
                </div>
                <div className="editor-grid">
                  <div className="field-group">
                    <label className="field-label">Language</label>
                    <input value={lang.language || ''} onChange={e => update(`languages.${i}.language`, e.target.value)} placeholder="English" />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Level</label>
                    <select value={lang.level || ''} onChange={e => update(`languages.${i}.level`, e.target.value)}>
                      <option value="">Select level</option>
                      {LANGUAGE_LEVELS.map(lv => <option key={lv} value={lv}>{lv}</option>)}
                    </select>
                  </div>
                </div>
              </div>
            ))}
            <button className="add-item-btn" onClick={() => addListItem('languages', { language: '', level: '' })}>
              <Plus size={14} /> Add Language
            </button>
          </>
        );

      case 'references':
        return (
          <textarea
            value={data.references || ''}
            onChange={e => update('references', e.target.value)}
            placeholder="Available upon request"
            rows={3}
          />
        );

      default:
        return null;
    }
  };

  return (
    <div className="resume-editor">
      {/* Personal Info: pinned at top, not draggable/removable */}
      <Section title="Personal Information" icon={<User size={15} />} defaultOpen={true} draggable={false}>
        <div className="editor-grid">
          <div className="field-group">
            <label className="field-label">Full Name</label>
            <input value={pi.name || ''} onChange={e => update('personal_info.name', e.target.value)} placeholder="John Doe" />
          </div>

          {STANDARD_PERSONAL_FIELDS.filter(isPersonalFieldActive).map((f) => {
            if (f.isPhoto) {
              return (
                <div className="field-group editor-full" key={f.key}>
                  <div className="field-header-row">
                    <label className="field-label">{f.label}</label>
                    <button
                      type="button"
                      className="field-remove-btn"
                      title={`Remove ${f.label}`}
                      onClick={() => removePersonalField(f.key)}
                    >
                      <X size={12} />
                    </button>
                  </div>
                  <div className="photo-upload-area">
                    {pi.photo_path ? (
                      <img className="photo-preview" src={photoApi.getUrl(pi.photo_path)} alt="Profile" />
                    ) : (
                      <div className="photo-placeholder"><User size={24} /></div>
                    )}
                    <button className="photo-upload-btn" type="button" onClick={() => fileInputRef.current?.click()}>
                      Upload Photo
                    </button>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/*"
                      style={{ display: 'none' }}
                      onChange={handlePhotoUpload}
                    />
                  </div>
                </div>
              );
            }

            return (
              <div className={`field-group ${f.isFull ? 'editor-full' : ''}`} key={f.key}>
                <div className="field-header-row">
                  <label className="field-label">{f.label}</label>
                  <button
                    type="button"
                    className="field-remove-btn"
                    title={`Remove ${f.label}`}
                    onClick={() => removePersonalField(f.key)}
                  >
                    <X size={12} />
                  </button>
                </div>
                <input
                  type={f.type || 'text'}
                  value={pi[f.key] || ''}
                  onChange={e => update(`personal_info.${f.key}`, e.target.value)}
                  placeholder={f.placeholder}
                />
              </div>
            );
          })}

          {Array.isArray(pi.custom_fields) && pi.custom_fields.map((cf, idx) => (
            <div className="custom-field-card" key={idx}>
              <div className="field-header-row">
                <span className="field-label" style={{ fontWeight: 650 }}>Custom Field #{idx + 1}</span>
                <button
                  type="button"
                  className="field-remove-btn"
                  title="Remove custom field"
                  onClick={() => removeCustomContactField(idx)}
                >
                  <X size={12} />
                </button>
              </div>
              <div className="custom-field-grid">
                <div className="field-group">
                  <label className="field-label">Label</label>
                  <input
                    value={cf.label || ''}
                    onChange={e => update(`personal_info.custom_fields.${idx}.label`, e.target.value)}
                    placeholder="e.g. Portfolio, Twitter"
                  />
                </div>
                <div className="field-group">
                  <label className="field-label">Display Value</label>
                  <input
                    value={cf.value || ''}
                    onChange={e => update(`personal_info.custom_fields.${idx}.value`, e.target.value)}
                    placeholder="e.g. x.com/username"
                  />
                </div>
                <div className="field-group">
                  <label className="field-label">Link URL (Optional)</label>
                  <input
                    value={cf.url || ''}
                    onChange={e => update(`personal_info.custom_fields.${idx}.url`, e.target.value)}
                    placeholder="https://..."
                  />
                </div>
              </div>
            </div>
          ))}

          <div className="personal-info-actions" ref={personalAddContainerRef}>
            <button
              type="button"
              className="personal-info-add-btn"
              onClick={() => setPersonalAddOpen(prev => !prev)}
            >
              <Plus size={13} /> Add Field
            </button>

            {personalAddOpen && (
              <div className="personal-info-add-menu">
                {availablePersonalFields.map(f => (
                  <button
                    key={f.key}
                    type="button"
                    className="personal-info-add-option"
                    onClick={() => {
                      addPersonalField(f.key);
                      setPersonalAddOpen(false);
                    }}
                  >
                    <Plus size={12} /> {f.label}
                  </button>
                ))}
                <button
                  type="button"
                  className="personal-info-add-option custom"
                  onClick={() => {
                    addCustomContactField();
                    setPersonalAddOpen(false);
                  }}
                >
                  <Plus size={12} /> Custom Field (Label & Value)
                </button>
              </div>
            )}
          </div>
        </div>
      </Section>

      {/* Dynamic, Draggable, Reorderable, Removable Sections */}
      {currentSectionOrder.map((sectionId, index) => {
        const meta = SECTION_METADATA[sectionId];
        if (!meta) return null;

        const isDragging = draggedIndex === index;
        const isDragOver = dragOverIndex === index && draggedIndex !== index;

        const sectionActions = (
          <>
            <button
              type="button"
              className="editor-section-action-btn"
              title="Move section up"
              disabled={index === 0}
              onClick={() => moveSection(index, -1)}
            >
              <ChevronUp size={14} />
            </button>
            <button
              type="button"
              className="editor-section-action-btn"
              title="Move section down"
              disabled={index === currentSectionOrder.length - 1}
              onClick={() => moveSection(index, 1)}
            >
              <ChevronDown size={14} />
            </button>
            {sectionId === 'about_me' && (
              <AISuggest
                sectionType="about_me"
                currentContent={data.about_me}
                onAccept={val => update('about_me', val)}
              />
            )}
            <button
              type="button"
              className="editor-section-action-btn remove"
              title={`Remove ${meta.title}`}
              onClick={() => removeSection(sectionId)}
            >
              <Trash2 size={13} />
            </button>
          </>
        );

        return (
          <Section
            key={sectionId}
            title={meta.title}
            icon={meta.icon}
            draggable={true}
            isDragging={isDragging}
            isDragOver={isDragOver}
            onDragStart={e => handleDragStart(e, index)}
            onDragOver={e => handleDragOver(e, index)}
            onDragLeave={handleDragLeave}
            onDrop={e => handleDrop(e, index)}
            onDragEnd={handleDragEnd}
            actions={sectionActions}
          >
            {renderSectionContent(sectionId)}
          </Section>
        );
      })}

      {/* Add Section / Reset Order Area */}
      <div className="add-section-container" ref={addSectionContainerRef}>
        <button
          type="button"
          className="add-section-toggle-btn"
          onClick={() => setAddSectionOpen(prev => !prev)}
          disabled={availableSections.length === 0}
        >
          <Plus size={15} />
          {availableSections.length > 0
            ? `Add Section (${availableSections.length} available)`
            : 'All Sections Added'}
        </button>

        {!isDefaultOrder && (
          <button
            type="button"
            className="reset-section-order-btn"
            title="Reset all sections to default order"
            onClick={resetSectionOrder}
          >
            <RotateCcw size={13} /> Reset Section Order
          </button>
        )}

        {addSectionOpen && availableSections.length > 0 && (
          <div className="add-section-dropdown">
            <div className="add-section-dropdown-header">Available Sections to Add</div>
            {availableSections.map(sec => (
              <button
                key={sec.id}
                type="button"
                className="add-section-option"
                onClick={() => {
                  addSection(sec.id);
                  setAddSectionOpen(false);
                }}
              >
                <span className="add-section-option-icon">{sec.icon}</span>
                <div className="add-section-option-text">
                  <span className="add-section-option-title">{sec.title}</span>
                  <span className="add-section-option-desc">{sec.description}</span>
                </div>
                <Plus size={14} className="add-section-option-plus" />
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function SkillsEditor({ skills, onChange }) {
  const [newSkillInputs, setNewSkillInputs] = useState({});
  const safeSkills = Array.isArray(skills) ? skills : [];

  const addCategory = () => {
    const newSkills = [...safeSkills, { category: '', items: [] }];
    onChange(newSkills);
  };

  const renameCategory = (index, newName) => {
    const newSkills = [...safeSkills];
    newSkills[index] = { ...newSkills[index], category: newName };
    onChange(newSkills);
  };

  const removeCategory = (index) => {
    const newSkills = [...safeSkills];
    newSkills.splice(index, 1);
    onChange(newSkills);
  };

  const addSkill = (index) => {
    const val = (newSkillInputs[index] || '').trim();
    if (!val) return;
    const newSkills = [...safeSkills];
    newSkills[index] = { ...newSkills[index], items: [...(newSkills[index].items || []), val] };
    onChange(newSkills);
    setNewSkillInputs(prev => ({ ...prev, [index]: '' }));
  };

  const removeSkill = (catIndex, skillIndex) => {
    const newSkills = [...safeSkills];
    const newItems = [...(newSkills[catIndex].items || [])];
    newItems.splice(skillIndex, 1);
    newSkills[catIndex] = { ...newSkills[catIndex], items: newItems };
    onChange(newSkills);
  };

  return (
    <>
      {safeSkills.map((catObj, catIdx) => (
        <div className="skill-category" key={catIdx}>
          <div className="skill-category-header">
            <input
              value={catObj.category || ''}
              onChange={e => renameCategory(catIdx, e.target.value)}
              placeholder="Category name"
              style={{ fontWeight: 600 }}
            />
            <button className="list-item-remove" onClick={() => removeCategory(catIdx)}><X size={12} /></button>
          </div>
          <div className="skill-chips">
            {(catObj.items || []).map((skill, j) => (
              <span className="skill-chip" key={j}>
                {skill}
                <button className="skill-chip-remove" onClick={() => removeSkill(catIdx, j)}><X size={10} /></button>
              </span>
            ))}
          </div>
          <div className="add-skill-input">
            <input
              value={newSkillInputs[catIdx] || ''}
              onChange={e => setNewSkillInputs(prev => ({ ...prev, [catIdx]: e.target.value }))}
              placeholder="Add a skill..."
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addSkill(catIdx); } }}
            />
            <button className="add-item-btn" style={{ width: 'auto', marginTop: 0, padding: '5px 12px' }} onClick={() => addSkill(catIdx)}><Plus size={14} /></button>
          </div>
        </div>
      ))}
      <button className="add-item-btn" onClick={addCategory}>
        <Plus size={14} /> Add Skill Category
      </button>
    </>
  );
}
