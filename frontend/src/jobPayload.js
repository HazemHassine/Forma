function text(value) {
  return String(value ?? '').trim() || null;
}

export function buildJobPayload(formData) {
  const resumeVersionId = formData.resume_version_id;

  return {
    company: String(formData.company ?? '').trim(),
    position: String(formData.position ?? '').trim(),
    url: text(formData.url),
    status: formData.status,
    resume_version_id: resumeVersionId === '' || resumeVersionId == null
      ? null
      : Number(resumeVersionId),
    notes: text(formData.notes),
    applied_at: formData.applied_at || null,
    job_description: text(formData.job_description),
    location: text(formData.location),
    salary: text(formData.salary),
    contact: text(formData.contact),
    next_step: text(formData.next_step),
    follow_up_at: formData.follow_up_at || null,
  };
}
