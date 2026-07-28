export function buildJobPayload(formData) {
  const resumeVersionId = formData.resume_version_id;

  return {
    company: formData.company.trim(),
    position: formData.position.trim(),
    url: formData.url.trim() || null,
    status: formData.status,
    resume_version_id: resumeVersionId === '' || resumeVersionId == null
      ? null
      : Number(resumeVersionId),
    notes: formData.notes.trim() || null,
    applied_at: formData.applied_at || null,
  };
}
