import { useState, useRef } from 'react';
import { User, MessageSquare, GraduationCap, Briefcase, Rocket, Microscope, Zap, Award, Globe, ClipboardList, X, ChevronDown, Plus } from 'lucide-react';
import { photoApi } from '../api';
import { useToast } from '../App';
import AISuggest from './AISuggest';
import './ResumeEditor.css';

const LANGUAGE_LEVELS = ['Native', 'C2', 'C1', 'B2', 'B1', 'A2', 'A1'];

function Section({ title, icon, children, defaultOpen = false, actions }) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="editor-section">
      <div className="editor-section-header" onClick={() => setOpen(!open)}>
        <div className="editor-section-header-left">
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

  if (!data) return null;

  const pi = data.personal_info || {};
  const education = data.education || [];
  const experience = data.work_experience || [];
  const projects = data.projects || [];
  const research = data.research || [];
  const skills = data.skills || [];
  const certificates = data.certificates || [];
  const languages = data.languages || [];

  return (
    <div className="resume-editor">
      {/* Personal Info */}
      <Section title="Personal Information" icon={<User size={15} />} defaultOpen={true}>
        <div className="editor-grid">
          <div className="field-group">
            <label className="field-label">Full Name</label>
            <input value={pi.name || ''} onChange={e => update('personal_info.name', e.target.value)} placeholder="John Doe" />
          </div>
          <div className="field-group">
            <label className="field-label">Professional Title</label>
            <input value={pi.title || ''} onChange={e => update('personal_info.title', e.target.value)} placeholder="Software Engineer" />
          </div>
          <div className="field-group">
            <label className="field-label">Email</label>
            <input type="email" value={pi.email || ''} onChange={e => update('personal_info.email', e.target.value)} placeholder="john@example.com" />
          </div>
          <div className="field-group">
            <label className="field-label">Phone</label>
            <input value={pi.phone || ''} onChange={e => update('personal_info.phone', e.target.value)} placeholder="+1 234 567 890" />
          </div>
          <div className="field-group editor-full">
            <label className="field-label">Address</label>
            <input value={pi.address || ''} onChange={e => update('personal_info.address', e.target.value)} placeholder="City, Country" />
          </div>
          <div className="field-group">
            <label className="field-label">GitHub</label>
            <input value={pi.github || ''} onChange={e => update('personal_info.github', e.target.value)} placeholder="github.com/username" />
          </div>
          <div className="field-group">
            <label className="field-label">LinkedIn</label>
            <input value={pi.linkedin || ''} onChange={e => update('personal_info.linkedin', e.target.value)} placeholder="linkedin.com/in/username" />
          </div>
          <div className="field-group editor-full">
            <label className="field-label">Photo</label>
            <div className="photo-upload-area">
              {pi.photo_path ? (
                <img className="photo-preview" src={photoApi.getCurrentUrl()} alt="Profile" />
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
        </div>
      </Section>

      {/* About Me */}
      <Section title="About Me" icon={<MessageSquare size={15} />} actions={
        <AISuggest sectionType="about_me" currentContent={data.about_me} onAccept={val => update('about_me', val)} />
      }>
        <div className="textarea-with-ai">
          <textarea
            value={data.about_me || ''}
            onChange={e => update('about_me', e.target.value)}
            placeholder="Write a brief professional summary..."
            rows={4}
          />
        </div>
      </Section>

      {/* Education */}
      <Section title="Education" icon={<GraduationCap size={15} />}>
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
      </Section>

      {/* Work Experience */}
      <Section title="Work Experience" icon={<Briefcase size={15} />}>
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
      </Section>

      {/* Projects */}
      <Section title="Projects" icon={<Rocket size={15} />}>
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
      </Section>

      {/* Research */}
      <Section title="Research" icon={<Microscope size={15} />}>
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
      </Section>

      {/* Skills */}
      <Section title="Skills" icon={<Zap size={15} />}>
        <SkillsEditor skills={skills} onChange={newSkills => {
          const newData = { ...data, skills: newSkills };
          onChange(newData);
        }} />
      </Section>

      {/* Certificates */}
      <Section title="Certificates" icon={<Award size={15} />}>
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
      </Section>

      {/* Languages */}
      <Section title="Languages" icon={<Globe size={15} />}>
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
      </Section>

      {/* References */}
      <Section title="References" icon={<ClipboardList size={15} />}>
        <textarea
          value={data.references || ''}
          onChange={e => update('references', e.target.value)}
          placeholder="Available upon request"
          rows={3}
        />
      </Section>
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
