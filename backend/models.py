from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class AIProvider(str, Enum):
    gemini = "gemini"
    chatgpt = "chatgpt"


class ResumeTemplate(str, Enum):
    modern = "modern"
    classic = "classic"
    minimal = "minimal"
    executive = "executive"
    creative = "creative"
    technical = "technical"


class PersonalInfo(BaseModel):
    name: str
    title: str
    address: str
    phone: str
    email: str
    github: str
    linkedin: str
    photo_path: Optional[str] = None


class EducationEntry(BaseModel):
    institution: str
    location: str
    degree: str
    dates: str
    details: Optional[str] = None


class WorkExperienceEntry(BaseModel):
    company: str
    location: str
    role: str
    dates: str
    bullets: list[str]


class ProjectEntry(BaseModel):
    name: str
    type: str = "Personal Project"
    description: str
    stack: str
    extra_info: Optional[str] = None
    bullets: list[str]


class ResearchEntry(BaseModel):
    title: str
    institution: str
    location: str
    date: str
    description: str
    focus: str


class SkillCategory(BaseModel):
    category: str
    items: list[str]


class CertificateEntry(BaseModel):
    name: str
    issuer: str


class LanguageEntry(BaseModel):
    language: str
    level: str


class ResumeData(BaseModel):
    personal_info: PersonalInfo
    about_me: str
    education: list[EducationEntry]
    work_experience: list[WorkExperienceEntry]
    projects: list[ProjectEntry]
    research: list[ResearchEntry]
    skills: list[SkillCategory]
    certificates: list[CertificateEntry]
    languages: list[LanguageEntry]
    references: str = "Available upon request"


class ResumeVersionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    data: ResumeData
    template_id: ResumeTemplate = ResumeTemplate.modern


class ResumeVersionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    data: Optional[ResumeData] = None
    template_id: Optional[ResumeTemplate] = None


class ResumeVersion(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    data: Optional[ResumeData] = None
    created_at: str
    is_current: bool
    template_id: ResumeTemplate = ResumeTemplate.modern


class ResumeVersionSummary(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: str
    is_current: bool
    template_id: ResumeTemplate = ResumeTemplate.modern


class ResumeTemplateOption(BaseModel):
    id: ResumeTemplate
    name: str
    description: str
    accent: str


class JobApplicationCreate(BaseModel):
    company: str
    position: str
    url: Optional[str] = None
    status: str = "applied"
    resume_version_id: Optional[int] = None
    applied_at: Optional[date] = None
    notes: Optional[str] = None


class JobApplicationUpdate(BaseModel):
    company: Optional[str] = None
    position: Optional[str] = None
    url: Optional[str] = None
    status: Optional[str] = None
    resume_version_id: Optional[int] = None
    applied_at: Optional[date] = None
    notes: Optional[str] = None


class JobApplication(BaseModel):
    id: int
    company: str
    position: str
    url: Optional[str] = None
    status: str
    resume_version_id: Optional[int] = None
    resume_version_name: Optional[str] = None
    applied_at: str
    notes: Optional[str] = None
    updated_at: Optional[str] = None


class AISuggestRequest(BaseModel):
    section_type: str
    current_content: str
    job_description: Optional[str] = None
    feedback: Optional[str] = None


class AISuggestResponse(BaseModel):
    suggestion: str


class OptimizeRequest(BaseModel):
    resume_version_id: int
    job_description: str
    target_role: Optional[str] = None
    company: Optional[str] = None
    instructions: Optional[str] = None


class OptimizeResponse(BaseModel):
    original: ResumeData
    optimized: ResumeData
    match_summary: Optional[str] = None
    strengths: list[str] = []
    gaps: list[str] = []
    keywords_used: list[str] = []


class ResumeDuplicateRequest(BaseModel):
    name: Optional[str] = None


class CoverLetterContent(BaseModel):
    company: str
    position: str
    recipient: str = "Hiring Team"
    subject: str
    date: str
    paragraphs: list[str] = Field(min_length=3, max_length=5)
    sign_off: str = "Best regards,"


class RoleRequirement(BaseModel):
    requirement: str
    importance: str


class EvidenceMatch(BaseModel):
    requirement: str
    resume_evidence: str
    relevance: str


class ClarificationQuestion(BaseModel):
    id: str
    question: str
    why: str
    placeholder: str


class AnalysisObservation(BaseModel):
    title: str
    detail: str
    impact: str


class CoverLetterAngle(BaseModel):
    id: str
    title: str
    approach: str
    supporting_evidence: list[str]
    caution: str


class ParagraphPlanItem(BaseModel):
    paragraph: int
    purpose: str
    evidence: str


class ExcludedClaim(BaseModel):
    claim: str
    reason: str


class CoverLetterAnalysis(BaseModel):
    company: str
    position: str
    role_summary: str
    key_requirements: list[RoleRequirement] = Field(default_factory=list, max_length=5)
    evidence_matches: list[EvidenceMatch] = Field(default_factory=list, max_length=5)
    gaps: list[str] = Field(default_factory=list, max_length=4)
    strategy: str
    questions: list[ClarificationQuestion] = Field(default_factory=list, max_length=3)
    observations: list[AnalysisObservation] = Field(
        default_factory=list,
        max_length=4,
    )
    angles: list[CoverLetterAngle] = Field(default_factory=list, max_length=3)
    recommended_angle_id: str = ""
    paragraph_plan: list[ParagraphPlanItem] = Field(
        default_factory=list,
        max_length=4,
    )
    excluded_claims: list[ExcludedClaim] = Field(
        default_factory=list,
        max_length=4,
    )


class CompanyInsight(BaseModel):
    fact: str
    relevance: str
    source_title: str
    source_url: str


class ResearchSource(BaseModel):
    title: str
    url: str


class CompanyResearchStatus(str, Enum):
    completed = "completed"
    limited = "limited"


class CompanyResearch(BaseModel):
    status: CompanyResearchStatus
    summary: str
    insights: list[CompanyInsight] = Field(default_factory=list)
    sources: list[ResearchSource] = Field(default_factory=list)


class CompanyResearchConfidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class CompanyIdentity(BaseModel):
    name: str
    legal_name: str
    website: str
    headquarters: str
    founded: str
    company_type: str
    employee_size: str
    industries: list[str] = Field(default_factory=list, max_length=6)
    source_urls: list[str] = Field(default_factory=list, max_length=5)


class SourcedCompanyText(BaseModel):
    text: str
    source_urls: list[str] = Field(default_factory=list, max_length=5)


class CompanyResearchItem(BaseModel):
    title: str
    detail: str
    source_urls: list[str] = Field(default_factory=list, max_length=4)


class CompanyResearchReportContent(BaseModel):
    identity: CompanyIdentity
    executive_summary: SourcedCompanyText
    products_services: list[CompanyResearchItem] = Field(
        default_factory=list,
        max_length=8,
    )
    business_model: list[CompanyResearchItem] = Field(
        default_factory=list,
        max_length=6,
    )
    customers_markets: list[CompanyResearchItem] = Field(
        default_factory=list,
        max_length=6,
    )
    leadership_ownership_funding: list[CompanyResearchItem] = Field(
        default_factory=list,
        max_length=8,
    )
    financial_signals: list[CompanyResearchItem] = Field(
        default_factory=list,
        max_length=6,
    )
    competitive_landscape: list[CompanyResearchItem] = Field(
        default_factory=list,
        max_length=6,
    )
    recent_developments: list[CompanyResearchItem] = Field(
        default_factory=list,
        max_length=8,
    )
    strategy_priorities: list[CompanyResearchItem] = Field(
        default_factory=list,
        max_length=6,
    )
    culture_workplace: list[CompanyResearchItem] = Field(
        default_factory=list,
        max_length=6,
    )
    risks_watchouts: list[CompanyResearchItem] = Field(
        default_factory=list,
        max_length=6,
    )
    role_relevance: list[CompanyResearchItem] = Field(
        default_factory=list,
        max_length=6,
    )
    follow_up_questions: list[str] = Field(default_factory=list, max_length=6)
    sources: list[ResearchSource] = Field(default_factory=list, max_length=20)
    researched_at: str
    confidence: CompanyResearchConfidence
    confidence_notes: str


class CompanyResearchReportRequest(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    website_url: Optional[str] = Field(default=None, max_length=2000)
    role: Optional[str] = Field(default=None, max_length=300)
    job_context: Optional[str] = Field(default=None, max_length=20000)
    focus: Optional[str] = Field(default=None, max_length=2000)


class CompanyResearchReport(BaseModel):
    id: int
    company: str
    website_url: Optional[str] = None
    role: Optional[str] = None
    job_context: Optional[str] = None
    focus: Optional[str] = None
    report: CompanyResearchReportContent
    created_at: str


class CompanyResearchReportSummary(BaseModel):
    id: int
    company: str
    legal_name: str
    website: str
    role: Optional[str] = None
    confidence: CompanyResearchConfidence
    researched_at: str
    created_at: str


class CoverLetterAnalyzeRequest(BaseModel):
    resume_version_id: int
    job_post: str = Field(min_length=80)
    source_url: Optional[str] = None
    company: Optional[str] = None
    position: Optional[str] = None
    instructions: Optional[str] = None


class CoverLetterResearchRequest(BaseModel):
    company: str = Field(min_length=1)
    position: str = Field(min_length=1)
    role_summary: str = Field(min_length=1)
    source_url: Optional[str] = None


class ClarificationAnswer(BaseModel):
    question_id: str
    question: str
    answer: str


class CoverLetterGenerationContext(BaseModel):
    provider: Optional[AIProvider] = None
    source_url: Optional[str] = None
    instructions: Optional[str] = None
    analysis: Optional[CoverLetterAnalysis] = None
    research: Optional[CompanyResearch] = None
    answers: list[ClarificationAnswer] = Field(default_factory=list)
    selected_angle_id: Optional[str] = None


class CoverLetterGenerateRequest(CoverLetterAnalyzeRequest):
    analysis: Optional[CoverLetterAnalysis] = None
    research: Optional[CompanyResearch] = None
    answers: list[ClarificationAnswer] = Field(default_factory=list)
    selected_angle_id: Optional[str] = None


class CoverLetterUpdate(BaseModel):
    company: Optional[str] = None
    position: Optional[str] = None
    recipient: Optional[str] = None
    subject: Optional[str] = None
    date: Optional[str] = None
    paragraphs: Optional[list[str]] = None
    sign_off: Optional[str] = None


class CoverLetter(BaseModel):
    id: int
    resume_version_id: int
    resume_version_name: Optional[str] = None
    company: str
    position: str
    source_url: Optional[str] = None
    job_post: str
    content: CoverLetterContent
    generation_context: Optional[CoverLetterGenerationContext] = None
    created_at: str
    updated_at: Optional[str] = None
