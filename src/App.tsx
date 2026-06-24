import { useEffect, useState, type ReactNode } from 'react'
import { AuthProvider, useAuth } from './context/AuthContext'
import { LoginScreen } from './components/LoginScreen'
import {
  runRequirementAgent,
  runAdoWriteBackAgent,
  runTestScenarioGenerationAgent,
  runAdoTestCaseWriteBackAgent,
  runRiskBasedTestPlannerAgent,
  runExecutionReadinessAgent,
  runTestManagerWriteBackAgent,
  runAutomationLinkAgent,
  runTestResultTriageAgent,
  runFinalReportMailAgent,
  parseTestGenerationAgentOutput,
  saveReviewMemoryToDataService,
  loadReviewMemoryFromDataService,
  buildScenarioKey,
  type RequirementAgentOutput,
  type QaLeadReview,
  type AdoTestCaseWriteBackOutput,
  type RiskBasedTestPlannerOutput,
  type TestScenarioGenerationOutput,
  type ExecutionReadinessOutput,
  type TestManagerWriteBackOutput,
  type AutomationLinkOutput,
  type AutomationLinkMapping,
  type TestManagerExecution,
  type TestResultTriageOutput,
  type TriageResult,
  type FinalReportMailOutput,
} from './services/orchestratorService'
import type { UiPathSDKConfig } from '@uipath/uipath-typescript/core'
import './App.css'

const authConfig: UiPathSDKConfig = {
  clientId: import.meta.env.VITE_UIPATH_CLIENT_ID,
  orgName: import.meta.env.VITE_UIPATH_ORG_NAME,
  tenantName: import.meta.env.VITE_UIPATH_TENANT_NAME,
  baseUrl: import.meta.env.VITE_UIPATH_BASE_URL,
  redirectUri: window.location.origin + window.location.pathname,
  scope: import.meta.env.VITE_UIPATH_SCOPE,
}

type QaAction =
  | 'Requirement Analysis'
  | 'Test Generation'
  | 'Test Execution'
  | 'Requirement Review'
  | 'Release Readiness'

type RunStatus = 'Idle' | 'Ready' | 'Running' | 'Completed' | 'Error'

type DecisionStatus = 'Idle' | 'Updating' | 'Updated' | 'Error'

type QaReviewDecision = 'Pending' | 'Approved' | 'Needs Changes' | 'Reject' | 'Clarification Requested'
type MemoryFeedbackDecision = 'Approve' | 'Needs Changes' | 'Reject' | ''
type MemoryFeedbackCategory =
  | 'Risk correction'
  | 'Missing gap'
  | 'Test focus improvement'
  | 'Readiness score correction'
  | 'Approval decision correction'
  | 'General feedback'
  | ''

const DEFAULT_APPROVAL_FEEDBACK =
  'Requirement approved for test scenario generation. Ensure generated test cases include mandatory field validation, duplicate patient validation, eligibility active/inactive/unavailable/timeout scenarios, appointment creation validation, audit trail validation, performance validation, and downstream API failure handling where applicable.'

type SidebarSection =
  | 'dashboard'
  | 'requirement-analysis'
  | 'test-generation'
  | 'test-execution'
  | 'requirement-review'
  | 'release-readiness'
  | 'execution-history'

type StepStatus = 'Pending' | 'Completed' | 'Warning' | 'Error'
type ExecutionStepStatus =
  | 'Pending'
  | 'Ready'
  | 'In Progress'
  | 'Completed'
  | 'Needs Attention'
  | 'Failed'

type DefectCreationResult = {
  testCaseId: string
  status: 'Completed' | 'InProgress' | 'Failed'
  output?: TestResultTriageOutput
  message: string
  classification?: string
  testManagerEvidenceLink?: string
}

type QaReportStatus = 'Sign-off Blocked' | 'Sign-off With Exceptions' | 'Sign-off Recommended'

type ExecutionHistoryItem = {
  requirementId: string
  submittedBy: string
  environment: string
  readinessStatus: string
  readinessScore: string | number
  riskLevel: string
  nextStep: string
  timestamp: string
}

type TestCaseReviewStatus = 'Pending' | 'Approved' | 'Rejected'

type EditableTestStep = {
  action: string
  expectedResult: string
}

type GeneratedTestScenario = NonNullable<TestScenarioGenerationOutput['testScenarios']>[number]

type ReviewedTestScenario = Omit<GeneratedTestScenario, 'steps'> & {
  scenarioKey?: string
  testCaseTitle?: string
  title?: string
  name?: string
  description?: string
  summary?: string
  steps?: unknown[]
  reviewStatus: TestCaseReviewStatus
  reviewComment: string
  reviewedAt: string
  reviewedBy: string
}

type TestCaseReviewMemory = {
  requirementId: string
  updatedAt: string
  scenarios: Array<{
    scenarioKey?: string
    title: string
    reviewStatus: TestCaseReviewStatus
    reviewComment: string
    reviewedAt: string
    reviewedBy: string
    scenario?: ReviewedTestScenario
  }>
}

const AUTOMATION_LINK_PROJECT_ID = '3dae45a4-6fc3-0000-60f6-0b49c244dbb8'
const AUTOMATION_LINK_PACKAGE_IDENTIFIER =
  import.meta.env.VITE_UIPATH_AUTOMATION_PACKAGE_IDENTIFIER ||
  'QualityOps Automated Execution Pack'
const AUTOMATION_LINK_PACKAGE_DISPLAY_NAME = 'QualityOps Automated Execution Pack'
const AUTOMATION_DEFAULT_ENTRY_POINT =
  import.meta.env.VITE_UIPATH_AUTOMATION_DEFAULT_ENTRY_POINT || 'Main.xaml'
const TEST_MANAGER_PROJECT_KEY =
  import.meta.env.VITE_UIPATH_TEST_MANAGER_PROJECT_KEY ||
  import.meta.env.VITE_UIPATH_TEST_MANAGER_PROJECT_ID ||
  import.meta.env.VITE_UIPATH_PROJECT_ID ||
  ''
const TRIAGE_CLASSIFICATIONS = [
  'Product Defect',
  'Automation Issue',
  'Environment Issue',
  'Data Issue',
  'Needs Review',
]

const friendlyAutomatedTestNames: Record<string, string> = {
  SIM_PASS_001: 'Functional Validation',
  SIM_ASSERTION_FAILURE_001: 'Business Rule Validation',
  SIM_AUTOMATION_UI_FAILURE_001: 'UI Interaction Validation',
  SIM_AUTOMATION_BROWSER_FAILURE_001: 'Browser Session Validation',
  SIM_AUTOMATION_SELECTOR_AMBIGUOUS_001: 'UI Selector Validation',
  SIM_ENVIRONMENT_FAILURE_001: 'Service Dependency Validation',
  SIM_ASSERTION_FAILURE_002: 'Data Verification',
  SIM_ENVIRONMENT_FAILURE_002: 'Test Data Connectivity Validation',
  SIM_PASS_002: 'Regression Validation',
  SIM_PASS_E2E_001: 'End-to-End Workflow Validation',
}

function sanitizeUserFacingText(value?: string): string {
  if (!value) {
    return ''
  }

  return value
    .replace(
      new RegExp(AUTOMATION_LINK_PACKAGE_IDENTIFIER, 'g'),
      AUTOMATION_LINK_PACKAGE_DISPLAY_NAME
    )
    .replace(/\bSimulator\b/gi, 'Execution Pack')
    .replace(/\bSimulation\b/gi, 'Execution')
    .replace(/\bMock\b/gi, 'Automated')
    .replace(/\bFake\b/gi, 'Automated')
    .replace(/\bAzureDevOps_PAT\b[^\n\r]*/gi, '[secret hidden]')
    .replace(/\bAuthorization\b[^\n\r]*/gi, '[authorization hidden]')
    .replace(/\bbearer\s+[A-Za-z0-9._~+/=-]+/gi, 'bearer [token hidden]')
    .replace(/\b(refresh token|client secret)\b[^\n\r]*/gi, '[secret hidden]')
}

function renderTechnicalText(value?: string): ReactNode {
  const displayValue = sanitizeUserFacingText(value)

  if (!displayValue) {
    return '-'
  }

  return displayValue.split(/([_./-])/).map((part, index) =>
    ['_', '.', '/', '-'].includes(part) ? (
      <span key={`${part}-${index}`}>
        {part}
        <wbr />
      </span>
    ) : (
      part
    )
  )
}

function formatTestGenerationMetadataValue(value: unknown): string {
  if (value === undefined || value === null || value === '') {
    return ''
  }

  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No'
  }

  if (Array.isArray(value)) {
    return value
      .map((item) => (typeof item === 'object' ? JSON.stringify(item) : String(item)))
      .join(', ')
  }

  if (typeof value === 'object') {
    return JSON.stringify(value)
  }

  return String(value)
}

function getTriageExecutions(output?: TestResultTriageOutput): TestManagerExecution[] {
  const executionSources = [
    output?.result?.data,
    output?.executions,
    output?.result?.executions,
    output?.data,
  ]

  const executions = executionSources.find((source) => Array.isArray(source)) ?? []

  return executions.map((execution) => ({
    ...execution,
    testExecutionId: execution.testExecutionId || execution.id,
    executionName: execution.executionName || execution.name,
    testSetId: execution.testSetId,
    status: execution.status,
    executionType: execution.executionType,
    runId: execution.runId,
  }))
}

function getTriageExecutionTotal(
  output: TestResultTriageOutput | undefined,
  executions: TestManagerExecution[]
): number {
  return output?.result?.paging?.total ?? executions.length
}

function getTriageErrorMessage(output?: TestResultTriageOutput | null): string {
  const blockedReasons = output?.result?.blockedReasons ?? output?.blockedReasons

  if (output?.result?.message) {
    return sanitizeUserFacingText(output.result.message)
  }

  if (blockedReasons?.length) {
    return sanitizeUserFacingText(blockedReasons.join(' '))
  }

  if (output?.message) {
    return sanitizeUserFacingText(output.message)
  }

  return 'Failed to load Test Manager executions.'
}

function getFriendlyAutomatedTestName(value?: string): string {
  if (!value) {
    return '-'
  }

  const match = value.match(/SIM_[A-Z0-9_]+/)
  const internalName = match?.[0] || value

  return friendlyAutomatedTestNames[internalName] || sanitizeUserFacingText(internalName)
}

function getMappingTestCaseId(mapping: AutomationLinkMapping, fallbackIndex: number): string {
  return String(
    mapping.testCaseId ||
      mapping.testManagerTestCaseId ||
      `Test Case ${fallbackIndex + 1}`
  )
}

function getMappingAutomatedTestCase(mapping: AutomationLinkMapping): string {
  return getFriendlyAutomatedTestName(
    mapping.automatedTestCase ||
      mapping.automatedTestCaseName ||
      mapping.automationTestCase
  )
}

function normalizeIdList(ids?: Array<string | number>): string[] {
  if (!ids?.length) {
    return []
  }

  return Array.from(new Set(ids.map((id) => String(id).trim()).filter(Boolean)))
}

function getFirstId(...ids: Array<string | number | undefined | null>): string {
  for (const id of ids) {
    if (id === undefined || id === null) {
      continue
    }

    const normalizedId = String(id).trim()

    if (normalizedId) {
      return normalizedId
    }
  }

  return ''
}

function getAdoParentIdFromValue(value?: string | number | null): string {
  if (value === undefined || value === null) {
    return ''
  }

  const normalizedValue = String(value).trim()

  if (!normalizedValue) {
    return ''
  }

  const prefixedMatch = normalizedValue.match(/(?:ADO|PBI|US|STORY|WORKITEM)[-\s_]*(\d+)/i)
  const numericMatch = normalizedValue.match(/\d+/)

  return prefixedMatch?.[1] || numericMatch?.[0] || normalizedValue
}

function getTriageResultKey(result: TriageResult, fallbackIndex: number): string {
  return `${result.testCaseId || `test-case-${fallbackIndex}`}-${result.variationId || 'default'}`
}

function getTriageExecutionSummary(
  output?: TestResultTriageOutput | null
) {
  return output?.result?.executionSummary ?? output?.executionSummary
}

function getTriageResults(output?: TestResultTriageOutput | null): TriageResult[] {
  return output?.result?.triageResults ?? output?.triageResults ?? []
}

function getTriageOverallRecommendation(output?: TestResultTriageOutput | null): string {
  return output?.result?.overallRecommendation ?? output?.overallRecommendation ?? ''
}

function getTriageStatus(output?: TestResultTriageOutput | null): string {
  return output?.result?.status ?? output?.status ?? ''
}

function normalizeClassification(value?: string): string {
  if (!value) {
    return 'Needs Review'
  }

  const normalizedValue = value.trim()
  return TRIAGE_CLASSIFICATIONS.includes(normalizedValue) ? normalizedValue : 'Needs Review'
}

function textContainsAny(value: string, terms: string[]): boolean {
  const normalizedValue = value.toLowerCase()
  return terms.some((term) => normalizedValue.includes(term.toLowerCase()))
}

function getDisplayClassification(result: TriageResult): string {
  const evidence = `${result.evidence || ''} ${Array.isArray(result.matchedTerms) ? result.matchedTerms.join(' ') : result.matchedTerms || ''}`
  const environmentTerms = [
    'HTTP 503',
    'Service Unavailable',
    'database connection timeout',
    'dependent API',
    'environment',
    'service did not respond',
    'timeout occurred while retrieving test data',
  ]
  const automationTerms = [
    'Could not find the user-interface',
    'UI element',
    'selector',
    'Strict selector failure',
    'Multiple similar matches',
    'Cannot communicate with the browser',
    'browser extension',
    'active session',
  ]

  if (textContainsAny(evidence, environmentTerms)) {
    return 'Environment Issue'
  }

  if (textContainsAny(evidence, automationTerms)) {
    return 'Automation Issue'
  }

  return normalizeClassification(result.classification)
}

function getClassificationClass(value?: string): string {
  return normalizeClassification(value).toLowerCase().replace(/\s+/g, '-')
}

function formatMatchedTerms(value?: string[] | string): string {
  if (Array.isArray(value)) {
    return value.length ? value.join(', ') : '-'
  }

  return value || '-'
}

function getClassificationRecommendation(classification?: string, fallback?: string): string {
  const normalizedClassification = normalizeClassification(classification)

  if (fallback?.trim()) {
    return sanitizeUserFacingText(fallback)
  }

  if (normalizedClassification === 'Environment Issue') {
    return 'Review environment availability, dependent services, credentials, and test data connectivity.'
  }

  if (normalizedClassification === 'Automation Issue') {
    return 'Review automation selector, browser, package, or workflow stability.'
  }

  if (normalizedClassification === 'Product Defect') {
    return 'Review the failed business behavior with product and create a defect with evidence.'
  }

  if (normalizedClassification === 'Data Issue') {
    return 'Review input data, test data setup, and expected data conditions.'
  }

  return 'Review the evidence and assign the correct triage owner.'
}

function redactTechnicalDetails(value?: string): string {
  if (!value) {
    return ''
  }

  return sanitizeUserFacingText(value)
    .replace(/\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/gi, '[technical id]')
    .replace(/https?:\/\/\S+/gi, '[endpoint hidden]')
    .replace(/\b(token|bearer|authorization)\b[^\n\r]*/gi, '[token diagnostics hidden]')
}

function getStructuredEvidenceSections(result: TriageResult) {
  const cleanedEvidence = redactTechnicalDetails(result.evidence)
  const lines = cleanedEvidence
    .split(/\r?\n|(?<=\.)\s+(?=[A-Z])/)
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => !/testcaselogid|testcaseid|jobkey|endpoint|token diagnostics/i.test(line))

  const sections = {
    failureSummary: [] as string[],
    errorException: [] as string[],
    robotLogs: [] as string[],
    assertions: [] as string[],
  }

  lines.forEach((line) => {
    if (/assert|expected|actual|validation/i.test(line)) {
      sections.assertions.push(line)
      return
    }

    if (/exception|error|failed|failure|timeout|unavailable|cannot|could not/i.test(line)) {
      sections.errorException.push(line)
      return
    }

    if (/robot|log|trace|workflow|selector|browser|host|machine|package/i.test(line)) {
      sections.robotLogs.push(line)
      return
    }

    sections.failureSummary.push(line)
  })

  const failureSummary =
    sections.failureSummary.length > 0
      ? sections.failureSummary.slice(0, 4).join('\n')
      : sections.errorException.slice(0, 2).join('\n') || 'No failure summary was provided.'

  return [
    ['Failure Summary', failureSummary, false],
    ['Error / Exception', sections.errorException.join('\n') || '-', false],
    ['Robot Logs', sections.robotLogs.join('\n') || '-', true],
    ['Assertions', sections.assertions.join('\n') || '-', false],
    [
      'Automation Details',
      [
        `Automation Test: ${sanitizeUserFacingText(result.automationTestCaseName || '-')}`,
        `Robot: ${sanitizeUserFacingText(result.robotName || '-')}`,
        `Host: ${sanitizeUserFacingText(result.hostMachine || '-')}`,
        `Matched Terms: ${sanitizeUserFacingText(formatMatchedTerms(result.matchedTerms))}`,
      ].join('\n'),
      false,
    ],
  ] as Array<[string, string, boolean]>
}

function getDefectStatusClass(value?: string): 'ready' | 'warning' | 'not-ready' {
  const normalizedValue = (value || '').toLowerCase()

  if (normalizedValue.includes('failed') || normalizedValue.includes('error')) {
    return 'not-ready'
  }

  if (normalizedValue.includes('progress') || normalizedValue.includes('pending')) {
    return 'warning'
  }

  return 'ready'
}

function getNumericReportValue(value?: number): number {
  return Number.isFinite(value) ? Number(value) : 0
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function cleanListItemText(value: string): string {
  return String(value || '')
    .replace(/\s+/g, ' ')
    .replace(/\s*\/\s*/g, '/')
    .replace(/\s*-\s*/g, '-')
    .replace(/\s+\./g, '.')
    .trim()
}

function AppContent() {
  const { isAuthenticated, isLoading, logout, uipathSDK } = useAuth()

  const [actionType, setActionType] = useState<QaAction>('Requirement Analysis')
  const [requirementId, setRequirementId] = useState('')
  const [submittedBy, setSubmittedBy] = useState('')
  const [environment, setEnvironment] = useState('SQA')
  const [status, setStatus] = useState<RunStatus>('Idle')
  const [statusMessage, setStatusMessage] = useState(
    'Select an action and provide the required details to start.'
  )
  const [agentOutput, setAgentOutput] = useState<RequirementAgentOutput | null>(null)
  const [executionHistory, setExecutionHistory] = useState<ExecutionHistoryItem[]>([])
  const [qaLeadDecision, setQaLeadDecision] = useState('')
  const [qaReviewDecision, setQaReviewDecision] = useState<QaReviewDecision>('Pending')
  const [memoryFeedbackDecision, setMemoryFeedbackDecision] =
    useState<MemoryFeedbackDecision>('')
  const [memoryFeedbackCategory, setMemoryFeedbackCategory] =
    useState<MemoryFeedbackCategory>('')
  const [memoryFeedbackText, setMemoryFeedbackText] = useState('')
  const [memoryFeedbackMessage, setMemoryFeedbackMessage] = useState('')
  const [memoryFeedbackError, setMemoryFeedbackError] = useState('')
  const [qaLeadReview, setQaLeadReview] = useState<QaLeadReview | null>(null)
  const [qaLeadReviewSaving, setQaLeadReviewSaving] = useState(false)
  const [adoCommentAdded, setAdoCommentAdded] = useState(false)
  const [decisionStatus, setDecisionStatus] = useState<DecisionStatus>('Idle')
  const [generatedScenarios, setGeneratedScenarios] =
    useState<ReviewedTestScenario[]>([])
  const [editingScenarioIndex, setEditingScenarioIndex] = useState<number | null>(null)
  const [scenarioEditDrafts, setScenarioEditDrafts] =
    useState<Record<number, ReviewedTestScenario>>({})
  const [reviewMemorySyncStatus, setReviewMemorySyncStatus] = useState(
    'Memory: Local + UiPath Data Service'
  )
  const [testGenerationResult, setTestGenerationResult] =
    useState<TestScenarioGenerationOutput | null>(null)
  const [testCaseWriteBackOutput, setTestCaseWriteBackOutput] =
    useState<AdoTestCaseWriteBackOutput | null>(null)
  const [isCreatingTestCases, setIsCreatingTestCases] = useState(false)
  const [riskPlanOutput, setRiskPlanOutput] = useState<RiskBasedTestPlannerOutput | null>(null)
  const [isGeneratingRiskPlan, setIsGeneratingRiskPlan] = useState(false)
  const [executionReadinessOutput, setExecutionReadinessOutput] =
    useState<ExecutionReadinessOutput | null>(null)
  const [isCheckingExecutionReadiness, setIsCheckingExecutionReadiness] = useState(false)
  const [testManagerWriteBackOutput, setTestManagerWriteBackOutput] =
    useState<TestManagerWriteBackOutput | null>(null)
  const [isSyncingTestManager, setIsSyncingTestManager] = useState(false)
  const [automationLinkResult, setAutomationLinkResult] =
    useState<AutomationLinkOutput | null>(null)
  const [automationLinkLoading, setAutomationLinkLoading] = useState(false)
  const [automationLinkError, setAutomationLinkError] = useState('')
  const [triageExecutions, setTriageExecutions] = useState<TestManagerExecution[]>([])
  const [selectedExecution, setSelectedExecution] = useState<TestManagerExecution | null>(null)
  const [triageAnalysisResult, setTriageAnalysisResult] =
    useState<TestResultTriageOutput | null>(null)
  const [triageLoadingExecutions, setTriageLoadingExecutions] = useState(false)
  const [triageAnalyzing, setTriageAnalyzing] = useState(false)
  const [triageCreatingDefects, setTriageCreatingDefects] = useState(false)
  const [triageError, setTriageError] = useState('')
  const [triageMessage, setTriageMessage] = useState('')
  const [selectedTriageResultKeys, setSelectedTriageResultKeys] = useState<string[]>([])
  const [expandedTriageResultKeys, setExpandedTriageResultKeys] = useState<string[]>([])
  const [triageClassificationOverrides, setTriageClassificationOverrides] =
    useState<Record<string, string>>({})
  const [adoParentStoryId, setAdoParentStoryId] = useState('')
  const [defectCreationResults, setDefectCreationResults] =
    useState<DefectCreationResult[]>([])
  const [finalReportGeneratedAt, setFinalReportGeneratedAt] = useState('')
  const [showFinalReportEmailForm, setShowFinalReportEmailForm] = useState(false)
  const [finalReportEmailTo, setFinalReportEmailTo] = useState('')
  const [finalReportEmailCc, setFinalReportEmailCc] = useState('')
  const [finalReportEmailSubject, setFinalReportEmailSubject] = useState('')
  const [finalReportEmailSending, setFinalReportEmailSending] = useState(false)
  const [finalReportEmailMessage, setFinalReportEmailMessage] = useState('')
  const [finalReportEmailError, setFinalReportEmailError] = useState('')
  const [finalReportEmailResult, setFinalReportEmailResult] =
    useState<FinalReportMailOutput | null>(null)
  const [activeSidebarSection, setActiveSidebarSection] = useState<SidebarSection>('dashboard')

  const cleanIdentifiedGaps =
    agentOutput?.requirementQualityAnalysis?.identifiedGaps
      ?.map(cleanListItemText)
      .filter(Boolean) ?? []
  const cleanSuggestedTestFocus =
    agentOutput?.qaAnalysisSummary?.suggestedTestFocus
      ?.map(cleanListItemText)
      .filter(Boolean) ?? []

  useEffect(() => {
    if (adoParentStoryId.trim()) {
      return
    }

    const possibleParentSources = [
      requirementId,
      (agentOutput as Record<string, unknown> | null)?.adoRequirementId,
      (agentOutput as Record<string, unknown> | null)?.workItemId,
      (agentOutput as Record<string, unknown> | null)?.pbiId,
      testCaseWriteBackOutput?.requirementId,
      (testCaseWriteBackOutput as Record<string, unknown> | null)?.adoRequirementId,
      (testCaseWriteBackOutput as Record<string, unknown> | null)?.workItemId,
      (testCaseWriteBackOutput as Record<string, unknown> | null)?.pbiId,
      testManagerWriteBackOutput?.requirementId,
      (testManagerWriteBackOutput as Record<string, unknown> | null)?.adoRequirementId,
      (testManagerWriteBackOutput as Record<string, unknown> | null)?.workItemId,
      (testManagerWriteBackOutput as Record<string, unknown> | null)?.pbiId,
    ]
    const inferredParentId =
      possibleParentSources.map((value) => getAdoParentIdFromValue(value as string | number)).find(Boolean) || ''

    if (inferredParentId) {
      setAdoParentStoryId(inferredParentId)
    }
  }, [adoParentStoryId, agentOutput, requirementId, testCaseWriteBackOutput, testManagerWriteBackOutput])

  useEffect(() => {
    const validRequirementId = requirementId.trim()

    setDecisionStatus('Idle')

    if (!validRequirementId) {
      setQaLeadReview(null)
      setQaReviewDecision('Pending')
      clearMemoryFeedbackState()
      return
    }

    const savedReview = localStorage.getItem(`qualityops_qaLeadReview_${validRequirementId}`)

    if (!savedReview) {
      setQaLeadReview(null)
      setQaReviewDecision('Pending')
      clearMemoryFeedbackState()
      return
    }

    try {
      const parsedReview = JSON.parse(savedReview) as QaLeadReview

      setQaLeadReview(parsedReview)
      setMemoryFeedbackDecision(parsedReview.decision as MemoryFeedbackDecision)
      setMemoryFeedbackCategory(parsedReview.feedbackCategory as MemoryFeedbackCategory)
      setMemoryFeedbackText(parsedReview.feedbackText)
      setQaReviewDecision(
        parsedReview.decision === 'Approve'
          ? 'Approved'
          : (parsedReview.decision as QaReviewDecision)
      )
      setQaLeadDecision(
        parsedReview.decision === 'Approve'
          ? 'Approved by QA Lead. Requirement is ready for test generation.'
          : `${parsedReview.decision} by QA Lead. Clarification required before test generation.`
      )
      setMemoryFeedbackMessage('QA Lead review memory loaded for this requirement.')
      setMemoryFeedbackError('')
    } catch {
      localStorage.removeItem(`qualityops_qaLeadReview_${validRequirementId}`)
    }
  }, [requirementId])

  const getTestCaseReviewMemoryKey = () =>
    `qualityops:testcase-review:${requirementId.trim() || 'latest'}`

  const getScenarioTitle = (
    scenario: {
      testCaseTitle?: string
      scenarioTitle?: string
      title?: string
      name?: string
    },
    index: number
  ) =>
    scenario.testCaseTitle ||
    scenario.title ||
    scenario.scenarioTitle ||
    scenario.name ||
    `Generated Test Scenario ${index + 1}`

  const getScenarioTitleByKey = (scenarioId?: string) => {
    if (!scenarioId) {
      return ''
    }

    const matchedScenario = generatedScenarios.find(
      (scenario) =>
        scenario.scenarioKey === scenarioId ||
        scenario.scenarioId === scenarioId
    )

    return (
      matchedScenario?.testCaseTitle ||
      matchedScenario?.title ||
      matchedScenario?.scenarioTitle ||
      matchedScenario?.name ||
      ''
    )
  }

  const getDisplayScenarioTitle = (
    item: {
      scenarioId?: string
      scenarioTitle?: string
      testCaseTitle?: string
      adoTestCaseTitle?: string
      title?: string
    },
    index: number
  ) => {
    const title =
      item.testCaseTitle ||
      item.adoTestCaseTitle ||
      item.title ||
      item.scenarioTitle ||
      getScenarioTitleByKey(item.scenarioId) ||
      item.scenarioId ||
      `Scenario ${index + 1}`
    const trimmedTitle = title.trim()
    const alreadyHasTsId = /^TS-\d+/i.test(trimmedTitle)

    if (alreadyHasTsId) {
      return trimmedTitle
    }

    return `TS-${String(index + 1).padStart(3, '0')} - ${trimmedTitle}`
  }

  const getScenarioKey = (
    scenario: {
      scenarioKey?: string
      scenarioTitle?: string
      title?: string
      name?: string
    },
    index: number
  ) =>
    scenario.scenarioKey ||
    buildScenarioKey(requirementId.trim() || 'latest', getScenarioTitle(scenario, index), index)

  const getScenarioDescription = (scenario: {
    description?: string
    summary?: string
    expectedResult?: string
  }) =>
    scenario.description ||
    scenario.summary ||
    scenario.expectedResult ||
    ''

  const normalizeStepForEdit = (step: unknown): EditableTestStep => {
    if (typeof step === 'string') {
      return {
        action: step,
        expectedResult: '',
      }
    }

    if (step && typeof step === 'object') {
      const record = step as Record<string, unknown>

      return {
        action: String(record.action || record.step || record.description || record.name || ''),
        expectedResult: String(
          record.expectedResult || record.expected || record.outcome || record.result || ''
        ),
      }
    }

    return {
      action: '',
      expectedResult: '',
    }
  }

  const getSavedTestCaseReviewMemory = (): TestCaseReviewMemory | null => {
    try {
      const savedReview = localStorage.getItem(getTestCaseReviewMemoryKey())
      return savedReview ? (JSON.parse(savedReview) as TestCaseReviewMemory) : null
    } catch {
      return null
    }
  }

  const saveTestCaseReviewMemory = (scenarios: ReviewedTestScenario[]) => {
    const reviewMemory: TestCaseReviewMemory = {
      requirementId: requirementId.trim(),
      updatedAt: new Date().toISOString(),
      scenarios: scenarios.map((scenario, index) => ({
        scenarioKey: getScenarioKey(scenario, index),
        title: getScenarioTitle(scenario, index),
        reviewStatus: scenario.reviewStatus,
        reviewComment: scenario.reviewComment,
        reviewedAt: scenario.reviewedAt,
        reviewedBy: scenario.reviewedBy,
        scenario,
      })),
    }

    localStorage.setItem(getTestCaseReviewMemoryKey(), JSON.stringify(reviewMemory))
  }

  const normalizeScenariosForReviewMemory = (
    scenarios: ReviewedTestScenario[]
  ): ReviewedTestScenario[] =>
    scenarios.map((scenario, index) => ({
      ...scenario,
      scenarioKey:
        scenario.scenarioKey ||
        buildScenarioKey(
          String(requirementId.trim() || 'latest'),
          scenario.title || scenario.name || scenario.scenarioTitle || getScenarioTitle(scenario, index),
          index
        ),
      reviewStatus: scenario.reviewStatus || 'Pending',
      reviewComment: scenario.reviewComment || '',
      reviewedBy: scenario.reviewedBy || '',
      reviewedAt: scenario.reviewedAt || '',
    }))

  const syncReviewMemory = async (updatedScenarios: ReviewedTestScenario[], reason: string) => {
    const scenariosWithKeys = normalizeScenariosForReviewMemory(updatedScenarios)
    const validRequirementId = requirementId.trim() || 'latest'

    console.log('Calling SAVE_REVIEW_MEMORY', {
      reason,
      requirementId: validRequirementId,
      count: scenariosWithKeys.length,
      statuses: scenariosWithKeys.map((scenario) => ({
        scenarioKey: scenario.scenarioKey,
        reviewStatus: scenario.reviewStatus,
      })),
    })

    try {
      await saveReviewMemoryToDataService(uipathSDK, validRequirementId, scenariosWithKeys)
      console.log('SAVE_REVIEW_MEMORY completed', reason)
      setReviewMemorySyncStatus('Review memory synced')
    } catch (error) {
      console.error('SAVE_REVIEW_MEMORY failed', error)
      setReviewMemorySyncStatus('Review saved locally. Data Service sync failed.')
    }
  }

  const prepareGeneratedScenariosForReview = (
    scenarios: NonNullable<TestScenarioGenerationOutput['testScenarios']>
  ): ReviewedTestScenario[] => {
    return scenarios.map((scenario, index) => {
      const title = getScenarioTitle(scenario, index)

      return {
        ...scenario,
        scenarioKey:
          scenario.scenarioKey ||
          buildScenarioKey(requirementId.trim() || 'latest', title, index),
        reviewStatus: 'Pending',
        reviewComment: scenario.reviewComment || '',
        reviewedAt: scenario.reviewedAt || '',
        reviewedBy: scenario.reviewedBy || '',
      }
    })
  }

  const mergeLocalReviewMemory = (scenarios: ReviewedTestScenario[]): ReviewedTestScenario[] => {
    const savedMemory = getSavedTestCaseReviewMemory()
    const savedByTitle = new Map(
      savedMemory?.scenarios.map((scenario) => [scenario.title, scenario]) ?? []
    )
    const savedByScenarioKey = new Map(
      savedMemory?.scenarios
        .filter((scenario) => scenario.scenarioKey)
        .map((scenario) => [scenario.scenarioKey, scenario]) ?? []
    )

    return scenarios.map((scenario, index) => {
      const title = getScenarioTitle(scenario, index)
      const scenarioKey = getScenarioKey(scenario, index)
      const savedReview = savedByScenarioKey.get(scenarioKey) || savedByTitle.get(title)
      const savedScenario = savedReview?.scenario

      return {
        ...scenario,
        ...savedScenario,
        scenarioKey:
          savedScenario?.scenarioKey ||
          savedReview?.scenarioKey ||
          scenario.scenarioKey ||
          buildScenarioKey(requirementId.trim() || 'latest', title, index),
        reviewStatus: savedReview?.reviewStatus || savedScenario?.reviewStatus || 'Pending',
        reviewComment: savedReview?.reviewComment || savedScenario?.reviewComment || '',
        reviewedAt: savedReview?.reviewedAt || savedScenario?.reviewedAt || '',
        reviewedBy: savedReview?.reviewedBy || savedScenario?.reviewedBy || '',
      }
    })
  }

  const getDataServiceReviewScenarios = (memoryOutput: unknown): Array<Record<string, unknown>> => {
    const output = memoryOutput as Record<string, any> | null
    const candidates =
      output?.scenarios ||
      output?.records ||
      output?.reviewMemory?.scenarios ||
      output?.data?.scenarios ||
      output?.data?.records ||
      []

    return Array.isArray(candidates) ? candidates : []
  }

  const getDataServiceRecordValue = (
    record: Record<string, unknown>,
    ...fieldNames: string[]
  ): unknown => {
    for (const fieldName of fieldNames) {
      const value = record[fieldName]

      if (value !== undefined && value !== null && value !== '') {
        return value
      }
    }

    return undefined
  }

  const mergeDataServiceReviewMemory = (
    scenarios: ReviewedTestScenario[],
    memoryOutput: unknown
  ): ReviewedTestScenario[] => {
    const records = getDataServiceReviewScenarios(memoryOutput)
    const recordsByKey = new Map(
      records.map((record) => [
        String(getDataServiceRecordValue(record, 'scenarioKey', 'ScenarioKey') || ''),
        record,
      ])
    )
    const recordsByTitle = new Map(
      records.map((record) => [
        String(
          getDataServiceRecordValue(
            record,
            'title',
            'Title',
            'scenarioTitle',
            'ScenarioTitle'
          ) || ''
        ),
        record,
      ])
    )

    return scenarios.map((scenario, index) => {
      const title = getScenarioTitle(scenario, index)
      const scenarioKey = getScenarioKey(scenario, index)
      const record = recordsByKey.get(scenarioKey) || recordsByTitle.get(title)

      if (!record) {
        return scenario
      }

      let savedScenario = scenario
      const scenarioJson = getDataServiceRecordValue(record, 'scenarioJson', 'ScenarioJson')
      if (typeof scenarioJson === 'string') {
        try {
          savedScenario = {
            ...savedScenario,
            ...JSON.parse(scenarioJson),
          }
        } catch {
          // Keep the generated scenario if stored JSON is not readable.
        }
      }

      return {
        ...savedScenario,
        scenarioKey:
          String(getDataServiceRecordValue(record, 'scenarioKey', 'ScenarioKey') || '') ||
          savedScenario.scenarioKey ||
          scenario.scenarioKey ||
          buildScenarioKey(requirementId.trim() || 'latest', title, index),
        reviewStatus:
          (getDataServiceRecordValue(
            record,
            'reviewStatus',
            'ReviewStatus'
          ) as TestCaseReviewStatus) || scenario.reviewStatus,
        reviewComment: String(
          getDataServiceRecordValue(record, 'reviewComment', 'ReviewComment') ||
            scenario.reviewComment ||
            ''
        ),
        reviewedAt: String(
          getDataServiceRecordValue(record, 'reviewedAt', 'ReviewedAt') ||
            scenario.reviewedAt ||
            ''
        ),
        reviewedBy: String(
          getDataServiceRecordValue(record, 'reviewedBy', 'ReviewedBy') ||
            scenario.reviewedBy ||
            ''
        ),
      }
    })
  }

  const updateGeneratedScenariosWithMemory = (
    updater: (scenarios: ReviewedTestScenario[]) => ReviewedTestScenario[],
    reason: string,
    syncDataService = false
  ) => {
    const nextScenarios = normalizeScenariosForReviewMemory(updater(generatedScenarios))
    setGeneratedScenarios(nextScenarios)
    saveTestCaseReviewMemory(nextScenarios)

    if (syncDataService) {
      void syncReviewMemory(nextScenarios, reason)
    }
  }

  const renderTestStep = (step: any) => {
    if (typeof step === 'string') {
      return step
    }

    if (step && typeof step === 'object') {
      return (
        <div>
          {step.action && (
            <div>
              <strong>Action:</strong> {step.action}
            </div>
          )}

          {step.expectedResult && (
            <div>
              <strong>Expected Result:</strong> {step.expectedResult}
            </div>
          )}
        </div>
      )
    }

    return String(step ?? '')
  }

  const getReviewCounts = () => ({
    total: generatedScenarios.length,
    approved: generatedScenarios.filter((scenario) => scenario.reviewStatus === 'Approved').length,
    rejected: generatedScenarios.filter((scenario) => scenario.reviewStatus === 'Rejected').length,
    pending: generatedScenarios.filter((scenario) => scenario.reviewStatus === 'Pending').length,
  })

  const updateScenarioReviewStatus = (
    scenarioIndex: number,
    reviewStatus: TestCaseReviewStatus
  ) => {
    const reviewedAt = reviewStatus === 'Pending' ? '' : new Date().toISOString()
    const reviewedBy = reviewStatus === 'Pending' ? '' : 'QA Lead'

    const updatedScenarios = generatedScenarios.map((scenario, index) =>
      index === scenarioIndex
        ? {
            ...scenario,
            reviewStatus,
            reviewedAt,
            reviewedBy,
          }
        : scenario
    )
    const scenariosWithKeys = normalizeScenariosForReviewMemory(updatedScenarios)

    setGeneratedScenarios(scenariosWithKeys)
    saveTestCaseReviewMemory(scenariosWithKeys)

    if (reviewStatus === 'Approved' || reviewStatus === 'Rejected') {
      const reason = reviewStatus === 'Approved' ? 'Approve' : 'Reject'
      const changedScenario = scenariosWithKeys[scenarioIndex]
      console.log(`Calling Memory Agent SAVE_REVIEW_MEMORY from ${reason}`, {
        requirementId: requirementId.trim() || 'latest',
        count: changedScenario ? 1 : 0,
        statuses: changedScenario
          ? [
              {
                scenarioKey: changedScenario.scenarioKey,
                reviewStatus: changedScenario.reviewStatus,
              },
            ]
          : [],
      })

      void saveReviewMemoryToDataService(
        uipathSDK,
        requirementId.trim() || 'latest',
        changedScenario ? [changedScenario] : []
      )
        .then((result) => {
          console.log('Memory Agent SAVE_REVIEW_MEMORY success', result)
          setReviewMemorySyncStatus('Review memory synced')
        })
        .catch((error) => {
          console.error('Memory Agent SAVE_REVIEW_MEMORY failed', error)
          setReviewMemorySyncStatus('Review saved locally. Data Service sync failed.')
        })
    }
  }

  const updateScenarioReviewComment = (scenarioIndex: number, reviewComment: string) => {
    updateGeneratedScenariosWithMemory(
      (scenarios) =>
        scenarios.map((scenario, index) =>
          index === scenarioIndex
            ? {
                ...scenario,
                reviewComment,
              }
            : scenario
        ),
      'Review Comment Change'
    )
  }

  const updateAllScenarioReviewStatuses = (reviewStatus: TestCaseReviewStatus) => {
    const reviewedAt = reviewStatus === 'Pending' ? '' : new Date().toISOString()
    const reviewedBy = reviewStatus === 'Pending' ? '' : 'QA Lead'

    updateGeneratedScenariosWithMemory(
      (scenarios) =>
        scenarios.map((scenario) => ({
          ...scenario,
          reviewStatus,
          reviewedAt,
          reviewedBy,
        })),
      reviewStatus === 'Approved'
        ? 'Approve All'
        : reviewStatus === 'Rejected'
          ? 'Reject All'
          : 'Reset Review',
      reviewStatus === 'Approved' || reviewStatus === 'Rejected'
    )
  }

  const startEditingScenario = (scenario: ReviewedTestScenario, scenarioIndex: number) => {
    setEditingScenarioIndex(scenarioIndex)
    setScenarioEditDrafts((drafts) => ({
      ...drafts,
      [scenarioIndex]: {
        ...scenario,
        title: getScenarioTitle(scenario, scenarioIndex),
        description: getScenarioDescription(scenario),
        steps: Array.isArray(scenario.steps) ? scenario.steps.map(normalizeStepForEdit) : [],
      },
    }))
  }

  const updateScenarioEditDraft = (
    scenarioIndex: number,
    updater: (scenario: ReviewedTestScenario) => ReviewedTestScenario
  ) => {
    setScenarioEditDrafts((drafts) => {
      const currentDraft = drafts[scenarioIndex]
      return currentDraft
        ? {
            ...drafts,
            [scenarioIndex]: updater(currentDraft),
          }
        : drafts
    })
  }

  const updateScenarioEditStep = (
    scenarioIndex: number,
    stepIndex: number,
    fieldName: keyof EditableTestStep,
    value: string
  ) => {
    updateScenarioEditDraft(scenarioIndex, (draft) => ({
      ...draft,
      steps: (draft.steps || []).map((step, index) => {
        const normalizedStep = normalizeStepForEdit(step)
        return index === stepIndex
          ? {
              ...normalizedStep,
              [fieldName]: value,
            }
          : normalizedStep
      }),
    }))
  }

  const saveScenarioEdit = (scenarioIndex: number) => {
    const draft = scenarioEditDrafts[scenarioIndex]

    if (!draft) {
      return
    }

    updateGeneratedScenariosWithMemory(
      (scenarios) =>
        scenarios.map((scenario, index) =>
          index === scenarioIndex
            ? {
                ...scenario,
                ...draft,
                scenarioTitle: draft.title || draft.scenarioTitle,
                title: draft.title || draft.scenarioTitle,
                description: draft.description || '',
                steps: Array.isArray(draft.steps) ? draft.steps.map(normalizeStepForEdit) : [],
                reviewStatus: scenario.reviewStatus === 'Approved' ? 'Approved' : 'Pending',
              }
            : scenario
        ),
      'Save Edit'
    )

    setEditingScenarioIndex(null)
    setScenarioEditDrafts((drafts) => {
      const nextDrafts = { ...drafts }
      delete nextDrafts[scenarioIndex]
      return nextDrafts
    })
  }

  const cancelScenarioEdit = (scenarioIndex: number) => {
    setEditingScenarioIndex(null)
    setScenarioEditDrafts((drafts) => {
      const nextDrafts = { ...drafts }
      delete nextDrafts[scenarioIndex]
      return nextDrafts
    })
  }

  const clearTriageState = () => {
    setTriageExecutions([])
    setSelectedExecution(null)
    setTriageAnalysisResult(null)
    setTriageLoadingExecutions(false)
    setTriageAnalyzing(false)
    setTriageCreatingDefects(false)
    setTriageError('')
    setTriageMessage('')
    setSelectedTriageResultKeys([])
    setExpandedTriageResultKeys([])
    setTriageClassificationOverrides({})
    setAdoParentStoryId(getAdoParentIdFromValue(requirementId))
    setDefectCreationResults([])
    setFinalReportGeneratedAt('')
    setShowFinalReportEmailForm(false)
    setFinalReportEmailTo('')
    setFinalReportEmailCc('')
    setFinalReportEmailSubject('')
    setFinalReportEmailSending(false)
    setFinalReportEmailMessage('')
    setFinalReportEmailError('')
    setFinalReportEmailResult(null)
  }

  const clearAutomationLinkState = () => {
    setAutomationLinkResult(null)
    setAutomationLinkError('')
    setAutomationLinkLoading(false)
    clearTriageState()
  }

  const clearMemoryFeedbackState = () => {
    setMemoryFeedbackDecision('')
    setMemoryFeedbackCategory('')
    setMemoryFeedbackText('')
    setMemoryFeedbackMessage('')
    setMemoryFeedbackError('')
    setQaLeadReview(null)
    setQaLeadReviewSaving(false)
    setAdoCommentAdded(false)
  }

  const clearTestGenerationState = () => {
    setGeneratedScenarios([])
    setEditingScenarioIndex(null)
    setScenarioEditDrafts({})
    setTestGenerationResult(null)
  }

  const navigationItems: Array<{ label: string; sectionId: SidebarSection }> = [
    { label: 'Dashboard', sectionId: 'dashboard' },
    { label: 'Requirement Analysis', sectionId: 'requirement-analysis' },
    { label: 'Requirement Review', sectionId: 'requirement-review' },
    { label: 'Test Generation', sectionId: 'test-generation' },
    { label: 'Test Execution', sectionId: 'test-execution' },
    { label: 'Release Readiness', sectionId: 'release-readiness' },
    { label: 'Execution History', sectionId: 'execution-history' },
  ]

  const isRequirementAnalysisCompleted = Boolean(agentOutput)
  const isRequirementReviewCompleted =
    decisionStatus === 'Updated' && qaReviewDecision === 'Approved'
  const isTestGenerationCompleted = generatedScenarios.length > 0
  const isAzureDevOpsSyncCompleted =
    (testCaseWriteBackOutput?.createdTestCases?.length ?? 0) > 0 ||
    testCaseWriteBackOutput?.writeBackStatus === 'Completed'
  const isRiskPlanCompleted = riskPlanOutput?.planningStatus === 'Completed'
  const isExecutionReadinessCompleted =
    executionReadinessOutput?.executionReadinessStatus?.toLowerCase() === 'ready'
  const isTestManagerSyncCompleted = testManagerWriteBackOutput?.syncStatus === 'Completed'
  const isAutomationMappingCompleted =
    automationLinkResult?.automationLinkStatus === 'Completed' ||
    (automationLinkResult?.linkedCount ?? 0) > 0
  const isAnalyzeTestResultsCompleted = Boolean(triageAnalysisResult)
  const isCreateAzureDevOpsBugCompleted = defectCreationResults.length > 0
  const isFinalQaReportCompleted = Boolean(finalReportGeneratedAt)
  const isSendQaReportEmailCompleted = Boolean(finalReportEmailResult) && !finalReportEmailError

  const workflowSteps: Array<{
    label: string
    sectionId: SidebarSection
    status: StepStatus
  }> = [
    {
      label: 'Requirement Analysis',
      sectionId: 'requirement-analysis',
      status: isRequirementAnalysisCompleted
        ? 'Completed'
        : status === 'Error'
          ? 'Error'
          : 'Pending',
    },
    {
      label: 'Requirement Review',
      sectionId: 'requirement-review',
      status:
        decisionStatus === 'Error'
          ? 'Error'
          : isRequirementReviewCompleted
            ? 'Completed'
            : 'Pending',
    },
    {
      label: 'Test Generation',
      sectionId: 'test-generation',
      status: isTestGenerationCompleted
        ? 'Completed'
        : qaLeadDecision === 'Test scenario generation failed.'
          ? 'Error'
          : 'Pending',
    },
    {
      label: 'Azure DevOps Sync',
      sectionId: 'test-execution',
      status: isAzureDevOpsSyncCompleted
        ? 'Completed'
        : status === 'Error' && statusMessage.toLowerCase().includes('ado test case')
          ? 'Error'
          : 'Pending',
    },
    {
      label: 'Risk-Based Plan',
      sectionId: 'release-readiness',
      status: isRiskPlanCompleted
        ? 'Completed'
        : status === 'Error' && statusMessage.toLowerCase().includes('risk-based')
          ? 'Error'
          : 'Pending',
    },
    {
      label: 'Execution Readiness',
      sectionId: 'test-execution',
      status: isExecutionReadinessCompleted
        ? 'Completed'
        : status === 'Error' && statusMessage.toLowerCase().includes('execution readiness')
          ? 'Error'
          : 'Pending',
    },
    {
      label: 'Test Manager Sync',
      sectionId: 'test-execution',
      status:
        ['ConfigurationRequired', 'ReadyToSync'].includes(
          testManagerWriteBackOutput?.syncStatus || ''
        )
          ? 'Warning'
          : isTestManagerSyncCompleted
            ? 'Completed'
            : status === 'Error' && statusMessage.toLowerCase().includes('test manager')
              ? 'Error'
              : 'Pending',
    },
    {
      label: 'Map Automated Test Cases',
      sectionId: 'test-execution',
      status: automationLinkError
        ? 'Error'
        : isAutomationMappingCompleted
          ? 'Completed'
          : 'Pending',
    },
    {
      label: 'Analyze Test Results',
      sectionId: 'test-execution',
      status: triageError
        ? 'Error'
        : isAnalyzeTestResultsCompleted
          ? 'Completed'
          : 'Pending',
    },
    {
      label: 'Create Azure DevOps Bug',
      sectionId: 'test-execution',
      status: defectCreationResults.some((item) => item.status === 'Failed')
        ? 'Error'
        : isCreateAzureDevOpsBugCompleted
          ? 'Completed'
          : 'Pending',
    },
    {
      label: 'Generate Final QA Report',
      sectionId: 'test-execution',
      status: isFinalQaReportCompleted ? 'Completed' : 'Pending',
    },
    {
      label: 'Send QA Report Email',
      sectionId: 'test-execution',
      status: finalReportEmailError
        ? 'Error'
        : isSendQaReportEmailCompleted
          ? 'Completed'
          : 'Pending',
    },
  ]

  if (isLoading) {
    return (
      <div className="loading-page">
        <div className="loader"></div>
        <span>Initializing UiPath connection...</span>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <LoginScreen />
  }

  const latestCreatedTestCaseIds = normalizeIdList(testManagerWriteBackOutput?.createdTestCaseIds)
  const latestReusedTestCaseIds = normalizeIdList(testManagerWriteBackOutput?.reusedTestCaseIds)
  const latestAllTestCaseIds = normalizeIdList(testManagerWriteBackOutput?.allTestCaseIds)
  const getTestManagerCaseResultStatus = (index: number) => {
    if (testManagerWriteBackOutput?.syncStatus === 'ReadyToSync') {
      return 'Prepared'
    }

    if (latestCreatedTestCaseIds[index]) {
      return 'Created'
    }

    if (latestReusedTestCaseIds[index]) {
      return 'Reused'
    }

    return testManagerWriteBackOutput?.syncStatus === 'Completed' ? 'Synced' : 'Prepared'
  }
  const getTestManagerCaseResultId = (index: number) =>
    latestCreatedTestCaseIds[index] ||
    latestReusedTestCaseIds[index] ||
    latestAllTestCaseIds[index] ||
    ''
  const latestAutomationLinkTestCaseIds =
    latestAllTestCaseIds.length > 0 ? latestAllTestCaseIds : latestCreatedTestCaseIds

  const canMapAutomatedTestCases = latestAutomationLinkTestCaseIds.length > 0
  const buildUiPathTestManagerProjectUrl = () => {
    const baseUrl = import.meta.env.VITE_UIPATH_BASE_URL || 'https://staging.uipath.com'
    const orgName = import.meta.env.VITE_UIPATH_ORG_NAME || ''
    const tenantName = import.meta.env.VITE_UIPATH_TENANT_NAME || ''

    if (!orgName || !tenantName || !TEST_MANAGER_PROJECT_KEY) {
      return ''
    }

    return `${baseUrl}/${orgName}/${tenantName}/testmanager_/projects/${TEST_MANAGER_PROJECT_KEY}/testsets`
  }
  const buildUiPathTestManagerTestSetUrl = (testSetId: string) => {
    const projectUrl = buildUiPathTestManagerProjectUrl()

    if (!testSetId || !projectUrl) {
      return ''
    }

    return `${projectUrl}/${encodeURIComponent(testSetId)}`
  }
  const latestTestSetId = getFirstId(
    (automationLinkResult as Record<string, unknown> | null)?.createdTestSetId as string | number | undefined,
    (automationLinkResult as Record<string, unknown> | null)?.createdTestSet as string | number | undefined,
    (automationLinkResult as Record<string, unknown> | null)?.testSetId as string | number | undefined,
    testManagerWriteBackOutput?.createdTestSetId,
    testManagerWriteBackOutput?.testManagerTestSetId,
    testManagerWriteBackOutput?.testSetId
  )
  const testManagerTestSetUrl =
    String(
      (automationLinkResult as Record<string, unknown> | null)?.createdTestSetUrl ||
        (automationLinkResult as Record<string, unknown> | null)?.testSetUrl ||
        (testManagerWriteBackOutput as Record<string, unknown> | null)?.createdTestSetUrl ||
        (testManagerWriteBackOutput as Record<string, unknown> | null)?.testSetUrl ||
        ''
    ) || buildUiPathTestManagerTestSetUrl(latestTestSetId)
  const testManagerProjectUrl = buildUiPathTestManagerProjectUrl()
  const canOpenTestManagerTestSet = Boolean(testManagerTestSetUrl || testManagerProjectUrl)
  const handleOpenTestSet = () => {
    const url = testManagerTestSetUrl || testManagerProjectUrl

    console.log('Opening UiPath Test Manager Test Set', {
      testSetId: latestTestSetId,
      testSetUrl: testManagerTestSetUrl,
      projectKey: TEST_MANAGER_PROJECT_KEY,
    })

    if (!url) {
      setAutomationLinkError(
        'Unable to open Test Set. Missing Test Manager project key or Test Set ID.'
      )
      return
    }

    window.open(url, '_blank', 'noopener,noreferrer')
  }
  const automationMappingCompleted = Boolean(automationLinkResult)
  const triageExecutionSummary = getTriageExecutionSummary(triageAnalysisResult)
  const failedTriageResults = getTriageResults(triageAnalysisResult)
  const hasSelectedFailedResults = selectedTriageResultKeys.length > 0
  const canCreateAdoBug = hasSelectedFailedResults && adoParentStoryId.trim().length > 0
  const classificationCounts = TRIAGE_CLASSIFICATIONS.reduce<Record<string, number>>(
    (counts, classification) => {
      counts[classification] = 0
      return counts
    },
    {}
  )

  failedTriageResults.forEach((triageResult, index) => {
    const resultKey = getTriageResultKey(triageResult, index)
    const classification =
      triageClassificationOverrides[resultKey] || getDisplayClassification(triageResult)
    classificationCounts[classification] = (classificationCounts[classification] ?? 0) + 1
  })
  const totalTests = getNumericReportValue(triageExecutionSummary?.totalTests)
  const passedTests = getNumericReportValue(triageExecutionSummary?.passed)
  const failedTests = getNumericReportValue(
    triageExecutionSummary?.failed ?? failedTriageResults.length
  )
  const skippedTests = getNumericReportValue(triageExecutionSummary?.skipped)
  const createdAdoBugs = defectCreationResults.filter(
    (defectResult) => defectResult.status === 'Completed'
  )
  const adoBugCountsByClassification = TRIAGE_CLASSIFICATIONS.reduce<Record<string, number>>(
    (counts, classification) => {
      counts[classification] = 0
      return counts
    },
    {}
  )

  defectCreationResults.forEach((defectResult) => {
    const classification = normalizeClassification(
      defectResult.output?.classification || defectResult.classification
    )
    adoBugCountsByClassification[classification] =
      (adoBugCountsByClassification[classification] ?? 0) + 1
  })

  const productDefectCount = classificationCounts['Product Defect'] ?? 0
  const automationIssueCount = classificationCounts['Automation Issue'] ?? 0
  const environmentIssueCount = classificationCounts['Environment Issue'] ?? 0
  const dataIssueCount = classificationCounts['Data Issue'] ?? 0
  const needsReviewCount = classificationCounts['Needs Review'] ?? 0
  const finalQaStatus: QaReportStatus =
    productDefectCount > 0
      ? 'Sign-off Blocked'
      : automationIssueCount > 0 || environmentIssueCount > 0
        ? 'Sign-off With Exceptions'
        : failedTests === 0
          ? 'Sign-off Recommended'
          : 'Sign-off With Exceptions'
  const finalQaRecommendation =
    productDefectCount > 0
      ? 'QA sign-off is blocked until product defects are fixed and retested.'
      : automationIssueCount > 0 || environmentIssueCount > 0
        ? 'QA sign-off can proceed only with exceptions after stakeholder approval.'
        : failedTests === 0
          ? 'QA sign-off is recommended.'
          : 'QA sign-off requires manual review.'
  const reportGeneratedDisplay = finalReportGeneratedAt || new Date().toLocaleString()
  const selectedExecutionName = sanitizeUserFacingText(
    selectedExecution?.executionName ||
      triageExecutionSummary?.executionName ||
      'Latest Test Manager Execution'
  )
  const adoBugLinks = defectCreationResults
    .map((defectResult) => defectResult.output?.adoBugUrl)
    .filter((value): value is string => Boolean(value))
  const testManagerExecutionLink =
    failedTriageResults.find((triageResult) => triageResult.linkToTestCaseLog)
      ?.linkToTestCaseLog || testManagerTestSetUrl
  const defaultFinalReportEmailSubject = `QA Sign-off Summary - ${selectedExecutionName}`
  const reportSummaryText = [
    'QualityOps QA Sign-off Report',
    `Parent PBI / Story ID: ${adoParentStoryId || '-'}`,
    `Execution: ${selectedExecutionName}`,
    `Status: ${finalQaStatus}`,
    `Tests: ${totalTests} total, ${passedTests} passed, ${failedTests} failed, ${skippedTests} skipped`,
    `Classifications: ${productDefectCount} product defects, ${automationIssueCount} automation issues, ${environmentIssueCount} environment issues, ${dataIssueCount} data issues, ${needsReviewCount} needs review`,
    `Azure DevOps Bugs Created: ${createdAdoBugs.length}`,
    `Recommendation: ${finalQaRecommendation}`,
  ].join('\n')
  const finalReportEmailText = [
    `Subject: ${defaultFinalReportEmailSubject}`,
    '',
    'Hi Team,',
    '',
    'Please find below the QA sign-off summary for the latest QualityOps automated test execution.',
    '',
    `Scope / Parent PBI: ${adoParentStoryId || '-'}`,
    `Execution summary: ${totalTests} total tests, ${passedTests} passed, ${failedTests} failed, ${skippedTests} skipped.`,
    `Triage summary: ${productDefectCount} product defects, ${automationIssueCount} automation issues, ${environmentIssueCount} environment issues, ${dataIssueCount} data issues, ${needsReviewCount} needs review.`,
    `Defects created: ${createdAdoBugs.length} Azure DevOps bug(s).`,
    '',
    'Risk observations:',
    '- Product defects block QA sign-off.',
    '- Automation issues should be reviewed by automation team.',
    '- Environment issues should be reviewed by environment/support team.',
    '- Needs Review items require manual QA validation.',
    '',
    `QA recommendation: ${finalQaRecommendation}`,
    '',
    'Next steps:',
    '- Product and QA teams to review blocking defects and retest fixes.',
    '- Automation and environment owners to review non-product failures.',
    '- Stakeholders to approve any sign-off exceptions before release.',
    '',
    'Regards,',
    'QualityOps QA Console',
  ].join('\n')
  const displayStatusMessage = sanitizeUserFacingText(statusMessage)

  const getReportHtml = () => {
    const metricRows = [
      ['Total Tests', totalTests],
      ['Passed', passedTests],
      ['Failed', failedTests],
      ['Skipped', skippedTests],
      ['Product Defects', productDefectCount],
      ['Automation Issues', automationIssueCount],
      ['Environment Issues', environmentIssueCount],
      ['Azure DevOps Bugs Created', createdAdoBugs.length],
    ]
    const triageRows = failedTriageResults
      .map((triageResult, index) => {
        const resultKey = getTriageResultKey(triageResult, index)
        const classification =
          triageClassificationOverrides[resultKey] || getDisplayClassification(triageResult)
        const action = getClassificationRecommendation(
          classification,
          triageResult.recommendedAction
        )
        const defect = defectCreationResults.find(
          (defectResult) =>
            defectResult.testCaseId === triageResult.testCaseId ||
            defectResult.testCaseId === resultKey
        )
        const bugId = defect?.output?.adoBugId || defect?.output?.defectId || '-'

        return `<tr><td>${escapeHtml(
          sanitizeUserFacingText(triageResult.testCaseName || triageResult.testCaseId || '-')
        )}</td><td>${escapeHtml(
          sanitizeUserFacingText(triageResult.resultStatus || 'Failed')
        )}</td><td>${escapeHtml(classification)}</td><td>${escapeHtml(
          action
        )}</td><td>${escapeHtml(String(bugId))}</td><td>${escapeHtml(
          sanitizeUserFacingText(triageResult.linkToTestCaseLog || '-')
        )}</td></tr>`
      })
      .join('')
    const defectRows = defectCreationResults
      .map((defectResult) => {
        const bugId = defectResult.output?.adoBugId || defectResult.output?.defectId || '-'
        const title = defectResult.output?.defectName || defectResult.message || 'Azure DevOps Bug'
        const classification =
          defectResult.output?.classification || defectResult.classification || '-'
        const parentId = defectResult.output?.adoParentId || adoParentStoryId || '-'
        const bugUrl = defectResult.output?.adoBugUrl || ''

        return `<tr><td>${escapeHtml(sanitizeUserFacingText(String(bugId)))}</td><td>${escapeHtml(
          sanitizeUserFacingText(title)
        )}</td><td>${escapeHtml(sanitizeUserFacingText(classification))}</td><td>${escapeHtml(
          sanitizeUserFacingText(parentId)
        )}</td><td>${
          bugUrl ? `<a href="${escapeHtml(bugUrl)}">Open Azure DevOps Bug</a>` : '-'
        }</td></tr>`
      })
      .join('')

    return `<!doctype html><html><head><meta charset="utf-8"><title>QualityOps QA Sign-off Report</title><style>body{font-family:Inter,Arial,sans-serif;margin:32px;color:#0f172a;background:#f8fafc}main{max-width:1120px;margin:auto;background:#fff;border:1px solid #dbe3ef;border-radius:16px;padding:24px}h1{color:#172554}.badge{display:inline-block;border-radius:999px;background:#dbeafe;color:#1d4ed8;font-weight:800;padding:8px 12px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card{border:1px solid #dbe3ef;border-radius:12px;padding:14px;background:#f8fafc}.card span{display:block;color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase}.card strong{font-size:26px}table{width:100%;border-collapse:collapse;margin-top:12px}th,td{border-bottom:1px solid #e2e8f0;padding:10px;text-align:left;vertical-align:top;font-size:13px}th{background:#f8fafc;color:#475569;text-transform:uppercase;font-size:11px}section{margin-top:24px}pre{white-space:pre-wrap;background:#f8fafc;border:1px solid #dbe3ef;border-radius:12px;padding:16px}</style></head><body><main><h1>QualityOps QA Sign-off Report</h1><p><strong>Parent PBI / Story ID:</strong> ${escapeHtml(
      sanitizeUserFacingText(adoParentStoryId || '-')
    )}</p><p><strong>Execution:</strong> ${escapeHtml(
      selectedExecutionName
    )}</p><p><strong>Generated:</strong> ${escapeHtml(
      reportGeneratedDisplay
    )}</p><span class="badge">${escapeHtml(
      finalQaStatus
    )}</span><section><h2>Executive Summary</h2><div class="grid">${metricRows
      .map(
        ([label, value]) =>
          `<div class="card"><span>${escapeHtml(String(label))}</span><strong>${escapeHtml(
            String(value)
          )}</strong></div>`
      )
      .join(
        ''
      )}</div></section><section><h2>Triage Summary</h2><table><thead><tr><th>Test Case</th><th>Result</th><th>Classification</th><th>Recommended Action</th><th>Azure DevOps Bug</th><th>Test Manager Evidence</th></tr></thead><tbody>${
      triageRows || '<tr><td colspan="6">No failed test results.</td></tr>'
    }</tbody></table></section><section><h2>Defect Summary</h2><table><thead><tr><th>Bug ID</th><th>Bug Title</th><th>Classification</th><th>Parent PBI</th><th>Open Azure DevOps Bug Link</th></tr></thead><tbody>${
      defectRows || '<tr><td colspan="5">No Azure DevOps bugs created.</td></tr>'
    }</tbody></table></section><section><h2>Risk / Observation</h2><ul><li>Product defects block QA sign-off.</li><li>Automation issues should be reviewed by automation team.</li><li>Environment issues should be reviewed by environment/support team.</li><li>Needs Review items require manual QA validation.</li></ul></section><section><h2>QA Recommendation</h2><p>${escapeHtml(
      finalQaRecommendation
    )}</p></section><section><h2>Email-style Sign-off Text</h2><pre>${escapeHtml(
      finalReportEmailText
    )}</pre></section></main></body></html>`
  }

  const handleGenerateFinalReport = () => {
    setFinalReportGeneratedAt(new Date().toLocaleString())
    setFinalReportEmailSubject(defaultFinalReportEmailSubject)
    setFinalReportEmailMessage('')
    setFinalReportEmailError('')
    setFinalReportEmailResult(null)
  }

  const handleShowFinalReportEmailForm = () => {
    setShowFinalReportEmailForm(true)
    setFinalReportEmailSubject((currentSubject) =>
      currentSubject.trim() ? currentSubject : defaultFinalReportEmailSubject
    )
    setFinalReportEmailMessage('')
    setFinalReportEmailError('')
  }

  const handleCopyText = async (value: string) => {
    await navigator.clipboard?.writeText(value)
  }

  const handleDownloadReportHtml = () => {
    const blob = new Blob([getReportHtml()], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `qualityops-final-qa-report-${Date.now()}.html`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  const handlePrintReport = () => {
    window.print()
  }

  const handleSendFinalReportEmail = async () => {
    const plainTextReport = String(finalReportEmailText || reportSummaryText || '').trim()
    const htmlReport = String(
      getReportHtml() || plainTextReport.replace(/\n/g, '<br/>')
    ).trim()
    const payload = {
      mode: 'sendFinalReportEmail' as const,
      to: String(finalReportEmailTo || '').trim(),
      cc: String(finalReportEmailCc || '').trim(),
      subject: String(finalReportEmailSubject || '').trim(),
      htmlReport,
      plainTextReport,
      executionName:
        selectedExecution?.name || triageExecutionSummary?.executionName || selectedExecutionName || '',
      adoBugLinks,
      testManagerExecutionLink: testManagerExecutionLink || '',
    }

    if (!payload.to) {
      setFinalReportEmailError('To email is required.')
      setFinalReportEmailMessage('')
      return
    }

    if (!payload.subject) {
      setFinalReportEmailError('Subject is required.')
      setFinalReportEmailMessage('')
      return
    }

    if (!payload.htmlReport && !payload.plainTextReport) {
      setFinalReportEmailError('Report content is required.')
      setFinalReportEmailMessage('')
      return
    }

    try {
      setFinalReportEmailSending(true)
      setFinalReportEmailError('')
      setFinalReportEmailMessage('Sending final QA report email...')
      setFinalReportEmailResult(null)
      console.log('Final report email payload debug', {
        to: payload.to,
        cc: payload.cc,
        subject: payload.subject,
        htmlReportLength: payload.htmlReport.length,
        plainTextReportLength: payload.plainTextReport.length,
      })

      const result = await runFinalReportMailAgent(
        uipathSDK,
        payload,
        (message) => {
          setFinalReportEmailMessage(sanitizeUserFacingText(message))
        }
      )

      setFinalReportEmailResult(result.output ?? null)
      setFinalReportEmailMessage('Final QA report email sent successfully.')
    } catch (error) {
      const errorMessage = sanitizeUserFacingText(
        error instanceof Error ? error.message : 'Failed to send final QA report email.'
      )

      setFinalReportEmailError(errorMessage)
      setFinalReportEmailMessage('')
    } finally {
      setFinalReportEmailSending(false)
    }
  }

  const handleRun = async () => {
    if (!requirementId.trim() || !submittedBy.trim()) {
      setStatus('Error')
      setStatusMessage('Requirement ID and Submitted By are mandatory.')
      setAgentOutput(null)
      clearTestGenerationState()
      setTestCaseWriteBackOutput(null)
      setRiskPlanOutput(null)
      setExecutionReadinessOutput(null)
      setTestManagerWriteBackOutput(null)
      clearAutomationLinkState()
      setQaLeadDecision('')
      setQaReviewDecision('Pending')
      setDecisionStatus('Idle')
      clearMemoryFeedbackState()
      return
    }

    if (actionType !== 'Requirement Analysis') {
      setStatus('Ready')
      setStatusMessage(`${actionType} module is prepared for future implementation.`)
      setAgentOutput(null)
      clearTestGenerationState()
      setTestCaseWriteBackOutput(null)
      setRiskPlanOutput(null)
      setExecutionReadinessOutput(null)
      setTestManagerWriteBackOutput(null)
      clearAutomationLinkState()
      setQaLeadDecision('')
      setQaReviewDecision('Pending')
      setDecisionStatus('Idle')
      clearMemoryFeedbackState()
      return
    }

    try {
      setStatus('Running')
      setAgentOutput(null)
      clearTestGenerationState()
      setTestCaseWriteBackOutput(null)
      setRiskPlanOutput(null)
      setExecutionReadinessOutput(null)
      setTestManagerWriteBackOutput(null)
      clearAutomationLinkState()
      setQaLeadDecision('')
      setQaReviewDecision('Pending')
      setDecisionStatus('Idle')
      clearMemoryFeedbackState()
      setStatusMessage('Starting QualityOps Requirement Coded Agent...')

      const result = await runRequirementAgent(
        uipathSDK,
        {
          requirementId: requirementId.trim(),
          submittedBy: submittedBy.trim(),
          environment,
        },
        (message) => {
          setStatusMessage(message)
        }
      )

      setAgentOutput(result.output ?? null)

      if (result.output) {
        const historyItem: ExecutionHistoryItem = {
          requirementId: requirementId.trim(),
          submittedBy: submittedBy.trim(),
          environment,
          readinessStatus: result.output.requirementQualityAnalysis?.readinessStatus || '-',
          readinessScore: result.output.requirementQualityAnalysis?.readinessScore ?? '-',
          riskLevel: result.output.qaAnalysisSummary?.riskLevel || '-',
          nextStep: result.output.qaAnalysisSummary?.nextStep || '-',
          timestamp: new Date().toLocaleString(),
        }

        setExecutionHistory((previous) => [historyItem, ...previous].slice(0, 5))
      }

      if (result.jobState === 'Successful') {
        setStatus('Completed')
        setStatusMessage(`${result.processingStatus} Job ID: ${result.jobId ?? 'N/A'}`)
      } else {
        setStatus('Ready')
        setStatusMessage(
          `${result.processingStatus} Job ID: ${result.jobId ?? 'N/A'}, State: ${
            result.jobState ?? 'N/A'
          }`
        )
      }
    } catch (error) {
      setStatus('Error')
      setAgentOutput(null)
      clearTestGenerationState()
      setTestCaseWriteBackOutput(null)
      setRiskPlanOutput(null)
      setExecutionReadinessOutput(null)
      setTestManagerWriteBackOutput(null)
      clearAutomationLinkState()
      setQaLeadDecision('')
      setQaReviewDecision('Pending')
      setDecisionStatus('Idle')
      clearMemoryFeedbackState()
      setStatusMessage(error instanceof Error ? error.message : 'Failed to run coded agent job.')
    }
  }

  const getQaLeadReviewCommentHtml = (review: QaLeadReview) => {
    const decision =
      review.decision === 'Approve'
        ? 'Approved'
        : review.decision === 'Needs Changes'
          ? 'Clarification Requested'
          : 'Rejected'
    const nextAction =
      review.decision === 'Approve'
        ? 'Requirement approved for test scenario generation.'
        : review.decision === 'Needs Changes'
          ? 'Requirement clarification is required before test generation.'
          : 'Requirement rejected. Requirement must be updated before QA can continue.'
    const identifiedGaps = review.originalIdentifiedGaps
      .map(cleanListItemText)
      .filter(Boolean)
    const identifiedGapsHtml = identifiedGaps.length
      ? `<ul>${identifiedGaps.map((gap) => `<li>${escapeHtml(gap)}</li>`).join('')}</ul>`
      : '<p>No gaps identified.</p>'

    return [
      '<h3>QualityOps QA Lead Review</h3>',
      '<table>',
      `<tr><td><b>Decision</b></td><td>${escapeHtml(decision)}</td></tr>`,
      `<tr><td><b>Feedback Category</b></td><td>${escapeHtml(review.feedbackCategory)}</td></tr>`,
      `<tr><td><b>Requirement ID</b></td><td>${escapeHtml(review.requirementId)}</td></tr>`,
      `<tr><td><b>Submitted By</b></td><td>${escapeHtml(review.submittedBy)}</td></tr>`,
      `<tr><td><b>Environment</b></td><td>${escapeHtml(environment)}</td></tr>`,
      `<tr><td><b>Readiness Status</b></td><td>${escapeHtml(review.originalReadinessStatus || '-')}</td></tr>`,
      `<tr><td><b>Readiness Score</b></td><td>${escapeHtml(review.originalReadinessScore || '-')}</td></tr>`,
      `<tr><td><b>Risk Level</b></td><td>${escapeHtml(review.originalRiskLevel || '-')}</td></tr>`,
      `<tr><td><b>Created At</b></td><td>${escapeHtml(review.createdAt)}</td></tr>`,
      '</table>',
      '<h4>Identified Gaps</h4>',
      identifiedGapsHtml,
      '<h4>QA Lead Feedback</h4>',
      `<p>${escapeHtml(review.feedbackText)}</p>`,
      '<h4>Next Action</h4>',
      `<p>${escapeHtml(nextAction)}</p>`,
    ].join('')
  }

  const handleSaveQaLeadReview = async () => {
    const validRequirementId = requirementId.trim()
    const validFeedbackText =
      memoryFeedbackDecision === 'Approve' && !memoryFeedbackText.trim()
        ? DEFAULT_APPROVAL_FEEDBACK
        : memoryFeedbackText.trim()

    if (!validRequirementId) {
      setMemoryFeedbackError('Requirement ID is required.')
      setMemoryFeedbackMessage('')
      return
    }

    if (!memoryFeedbackDecision) {
      setMemoryFeedbackError('QA Lead Decision is required.')
      setMemoryFeedbackMessage('')
      return
    }

    if (!memoryFeedbackCategory) {
      setMemoryFeedbackError('Feedback Category is required.')
      setMemoryFeedbackMessage('')
      return
    }

    if (
      ['Needs Changes', 'Reject'].includes(memoryFeedbackDecision) &&
      !validFeedbackText
    ) {
      setMemoryFeedbackError('Please add QA Lead feedback before saving this review.')
      setMemoryFeedbackMessage('')
      return
    }

    const originalIdentifiedGaps = cleanIdentifiedGaps
    const originalSuggestedTestFocus = cleanSuggestedTestFocus
    const createdAt = new Date().toISOString()
    const reviewMemory: QaLeadReview = {
      requirementId: validRequirementId,
      requirementTitle: agentOutput?.requirementTitle || '',
      decision: memoryFeedbackDecision,
      feedbackCategory: memoryFeedbackCategory,
      feedbackText: validFeedbackText,
      originalRiskLevel: agentOutput?.qaAnalysisSummary?.riskLevel || '',
      originalReadinessStatus:
        agentOutput?.requirementQualityAnalysis?.readinessStatus || '',
      originalReadinessScore: String(
        agentOutput?.requirementQualityAnalysis?.readinessScore ?? ''
      ),
      originalIdentifiedGaps,
      originalSuggestedTestFocus,
      submittedBy: 'Dhruba',
      createdAt,
    }

    localStorage.setItem(
      `qualityops_qaLeadReview_${validRequirementId}`,
      JSON.stringify(reviewMemory)
    )

    const isApproved = memoryFeedbackDecision === 'Approve'

    setQaLeadReview(reviewMemory)
    setMemoryFeedbackText(validFeedbackText)
    setMemoryFeedbackError('')
    setMemoryFeedbackMessage('Saving QA Lead review and writing comment to Azure DevOps...')
    setDecisionStatus('Updated')
    setQaReviewDecision(isApproved ? 'Approved' : memoryFeedbackDecision)
    setStatus(isApproved ? 'Completed' : 'Ready')
    setAdoCommentAdded(false)
    setQaLeadDecision(
      isApproved
        ? 'Approved by QA Lead. Requirement is ready for test generation.'
        : `${memoryFeedbackDecision} by QA Lead. Clarification required before test generation.`
    )
    setStatusMessage(
      isApproved
        ? 'QA Lead review saved. Requirement approved for test generation.'
        : 'Requirement review saved. Requirement clarification is required before test generation.'
    )

    try {
      setQaLeadReviewSaving(true)
      const commentHtml = getQaLeadReviewCommentHtml(reviewMemory)

      await runAdoWriteBackAgent(
        uipathSDK,
        {
          mode: 'writeRequirementReviewComment',
          requirementId: validRequirementId,
          commentTitle: 'QualityOps QA Lead Review',
          qaLeadReview: reviewMemory,
          commentHtml,
          submittedBy: reviewMemory.submittedBy,
          environment,
          decisionType: isApproved ? 'Approved' : 'Clarification Requested',
          decisionComment: commentHtml,
        },
        (message) => {
          setStatusMessage(sanitizeUserFacingText(message))
        }
      )

      setAdoCommentAdded(true)
      setMemoryFeedbackMessage('QA Lead review saved and written back to Azure DevOps.')
      setMemoryFeedbackError('')
      setStatusMessage(
        isApproved
          ? 'QA Lead review saved and written back to Azure DevOps. Requirement approved for test generation.'
          : 'QA Lead review saved and written back to Azure DevOps. Requirement clarification is required before test generation.'
      )
    } catch (error) {
      const errorMessage = sanitizeUserFacingText(
        error instanceof Error ? error.message : 'Unknown Azure DevOps writeback error.'
      )

      setAdoCommentAdded(false)
      setMemoryFeedbackMessage('')
      setMemoryFeedbackError(
        `QA Lead review saved locally, but Azure DevOps comment failed: ${errorMessage}`
      )
      setStatusMessage(
        `QA Lead review saved locally, but Azure DevOps comment failed: ${errorMessage}`
      )
    } finally {
      setQaLeadReviewSaving(false)
    }
  }

  const handleGenerateTests = async () => {
    if (!agentOutput) {
      setStatus('Error')
      setStatusMessage('Run Requirement Analysis before generating test scenarios.')
      return
    }

    if (qaReviewDecision !== 'Approved') {
      setStatus('Ready')
      setStatusMessage('Requirement Review approval is required before generating test scenarios.')
      setQaLeadDecision('Clarification required before test generation.')
      return
    }

    if (!qaLeadReview) {
      setStatus('Ready')
      setStatusMessage('No QA Lead review memory found. Please complete Requirement Review before generating test scenarios.')
      return
    }

    try {
      setActionType('Test Generation')
      setStatus('Running')
      clearTestGenerationState()
      setTestCaseWriteBackOutput(null)
      setRiskPlanOutput(null)
      setExecutionReadinessOutput(null)
      setTestManagerWriteBackOutput(null)
      clearAutomationLinkState()
      setQaLeadDecision('Generating test scenarios from requirement analysis output.')
      setStatusMessage('Starting Test Scenario Generation job...')

      const result = await runTestScenarioGenerationAgent(
        uipathSDK,
        {
          requirementId: requirementId.trim(),
          submittedBy: submittedBy.trim(),
          environment,
          requirementAnalysis: agentOutput,
          qaLeadReview,
          requirementTitle: agentOutput.requirementTitle,
          requirementDescription: agentOutput.requirementDescription,
          acceptanceCriteria: agentOutput.acceptanceCriteria,
          riskLevel: agentOutput.qaAnalysisSummary?.riskLevel,
          testingScope: agentOutput.qaAnalysisSummary?.testingScope,
          suggestedTestFocus: agentOutput.qaAnalysisSummary?.suggestedTestFocus,
        },
        (message) => {
          setStatusMessage(message)
        }
      )

      console.log('Test Generation run result:', result)
      console.log('Test Generation service output:', result.output)
      console.log('Test Generation raw job:', result.raw)

      if (result.jobState !== 'Successful') {
        setStatus('Running')
        setQaLeadDecision('Test scenario generation is still running.')
        setStatusMessage(
          `${result.processingStatus} Job ID: ${result.jobId ?? 'N/A'}, State: ${
            result.jobState ?? 'N/A'
          }`
        )
        return
      }

      const parsedOutput =
        result.output ??
        parseTestGenerationAgentOutput(result.raw) ??
        parseTestGenerationAgentOutput(result)
      console.log('Final parsed Test Generation Output:', parsedOutput)

      const scenarios = Array.isArray(parsedOutput?.testScenarios)
        ? parsedOutput.testScenarios
        : []
      console.log('Final parsed test scenarios count:', scenarios.length)

      const reviewedScenarios = prepareGeneratedScenariosForReview(scenarios)
      console.log('Generated scenarios with review status:', reviewedScenarios)
      setGeneratedScenarios(reviewedScenarios)
      saveTestCaseReviewMemory(reviewedScenarios)
      setReviewMemorySyncStatus('Memory: Local + UiPath Data Service')
      loadReviewMemoryFromDataService(uipathSDK, requirementId.trim() || 'latest')
        .then((memoryOutput) => {
          if (!memoryOutput) {
            return
          }

          const dataServiceRecords = getDataServiceReviewScenarios(memoryOutput)
          if (dataServiceRecords.length === 0) {
            setReviewMemorySyncStatus('Review memory synced')
            return
          }

          const mergedScenarios = mergeDataServiceReviewMemory(reviewedScenarios, memoryOutput)
          console.log('Generated scenarios with review status:', mergedScenarios)
          setGeneratedScenarios(mergedScenarios)
          saveTestCaseReviewMemory(mergedScenarios)
          setReviewMemorySyncStatus('Review memory synced')
        })
        .catch((error) => {
          console.warn('Review memory Data Service load failed; using local memory', error)
          const localScenarios = mergeLocalReviewMemory(reviewedScenarios)
          console.log('Generated scenarios with review status:', localScenarios)
          setGeneratedScenarios(localScenarios)
          saveTestCaseReviewMemory(localScenarios)
          setReviewMemorySyncStatus('Review saved locally. Data Service sync failed.')
        })
      setTestGenerationResult(parsedOutput ?? null)
      setStatus('Completed')

      setQaLeadDecision('Test scenarios generated from requirement analysis output.')
      setStatusMessage(
        scenarios.length === 0
          ? 'Test Scenario Generation completed, but UI could not find testScenarios in output.'
          : `${result.processingStatus} Job ID: ${result.jobId ?? 'N/A'}, State: ${
              result.jobState ?? 'N/A'
            }`
      )
    } catch (error) {
      setStatus('Error')
      clearTestGenerationState()
      setTestCaseWriteBackOutput(null)
      setRiskPlanOutput(null)
      setExecutionReadinessOutput(null)
      setTestManagerWriteBackOutput(null)
      clearAutomationLinkState()
      setQaLeadDecision('Test scenario generation failed.')
      setStatusMessage(
        error instanceof Error ? error.message : 'Failed to generate test scenarios.'
      )
    }
  }

  const handleCreateTestCases = async () => {
    console.log('Create Approved Test Cases button clicked')

    if (!generatedScenarios.length) {
      setStatus('Error')
      setStatusMessage('Generate test scenarios before creating Azure DevOps test cases.')
      return
    }

    const scenariosForCreation = generatedScenarios.map((scenario, index) => ({
      ...scenario,
      scenarioKey: getScenarioKey(scenario, index),
    }))

    const approvedScenarios = scenariosForCreation.flatMap((scenario, index) =>
      scenario.reviewStatus === 'Approved'
        ? [
            {
              scenarioKey: scenario.scenarioKey,
              title: getScenarioTitle(scenario, index),
              description: getScenarioDescription(scenario),
              priority: scenario.priority,
              steps: scenario.steps,
              reviewStatus: scenario.reviewStatus,
              reviewComment: scenario.reviewComment,
              reviewedAt: scenario.reviewedAt,
              reviewedBy: scenario.reviewedBy,
            },
          ]
        : []
    )

    if (!approvedScenarios.length) {
      setStatus('Error')
      setStatusMessage(
        'Please approve at least one test case before creating test cases in Azure DevOps.'
      )
      return
    }

    try {
      setActionType('Test Generation')
      setStatus('Running')
      setIsCreatingTestCases(true)
      setTestCaseWriteBackOutput(null)
      setExecutionReadinessOutput(null)
      setTestManagerWriteBackOutput(null)
      clearAutomationLinkState()
      setStatusMessage('Starting Azure DevOps Test Case WriteBack job...')

      console.log('Before ADO create - review counts:', {
        approved: scenariosForCreation.filter((scenario) => scenario.reviewStatus === 'Approved').length,
        rejected: scenariosForCreation.filter((scenario) => scenario.reviewStatus === 'Rejected').length,
        pending: scenariosForCreation.filter((scenario) => scenario.reviewStatus === 'Pending').length,
      })
      console.log('Total scenarios:', scenariosForCreation.length)
      console.log('Approved scenarios:', approvedScenarios.length)
      console.log('Approved scenarios sent to ADO:', approvedScenarios.length)
      console.log('Approved scenario keys:', approvedScenarios.map((scenario) => scenario.scenarioKey))
      console.log('Calling ADO TestCase WriteBack Agent now...')
      // TODO: Re-enable Data Service memory sync after Create Approved Test Cases flow is stable.

      const result = await runAdoTestCaseWriteBackAgent(
        uipathSDK,
        {
          requirementId: requirementId.trim(),
          submittedBy: submittedBy.trim(),
          environment,
          testScenarios: approvedScenarios as any,
        },
        (message) => {
          setStatusMessage(message)
        }
      )

      setTestCaseWriteBackOutput(result.output ?? null)

      if (result.output?.createdTestCases?.length) {
        const createdTestCasesWithScenarioKeys = result.output.createdTestCases.map(
          (created, index) => ({
            ...created,
            scenarioKey: created.scenarioKey || approvedScenarios[index]?.scenarioKey,
            adoTestCaseId:
              created.adoTestCaseId ||
              created.id ||
              created.testCaseId ||
              created.workItemId ||
              '',
            adoUrl: created.adoUrl || created.url || created.webUrl || '',
          })
        )

        console.log('Created test cases with scenario keys:', createdTestCasesWithScenarioKeys)
        // TODO: Re-enable Data Service memory sync after Create Approved Test Cases flow is stable.
      } else {
        console.log('TODO: ADO WriteBack response did not include created test case IDs to sync.')
      }

      if (result.jobState === 'Successful') {
        setStatus('Completed')
      } else {
        setStatus('Ready')
      }

      const createdCount = result.output?.createdTestCases?.length || approvedScenarios.length
      console.log('After ADO create - review counts should be unchanged:', {
        approved: generatedScenarios.filter((scenario) => scenario.reviewStatus === 'Approved').length,
        rejected: generatedScenarios.filter((scenario) => scenario.reviewStatus === 'Rejected').length,
        pending: generatedScenarios.filter((scenario) => scenario.reviewStatus === 'Pending').length,
      })
      setStatusMessage(`Created ${createdCount} approved test case(s) in Azure DevOps.`)
    } catch (error) {
      setStatus('Error')
      setTestCaseWriteBackOutput(null)
      setTestManagerWriteBackOutput(null)
      clearAutomationLinkState()
      setStatusMessage(
        error instanceof Error ? error.message : 'Failed to create Azure DevOps test cases.'
      )
    } finally {
      setIsCreatingTestCases(false)
    }
  }

  const handleGenerateRiskPlan = async () => {
    if (!agentOutput) {
      setStatus('Error')
      setStatusMessage('Run Requirement Analysis before generating a risk-based execution plan.')
      return
    }

    if (!generatedScenarios.length) {
      setStatus('Error')
      setStatusMessage('Generate test scenarios before generating a risk-based execution plan.')
      return
    }

    const scenariosWithKeys = normalizeScenariosForReviewMemory(generatedScenarios)
    const approvedScenarios = scenariosWithKeys.filter(
      (scenario) => scenario.reviewStatus === 'Approved'
    )
    const createdTestCases = testCaseWriteBackOutput?.createdTestCases || []

    if (!approvedScenarios.length || !createdTestCases.length) {
      setStatus('Error')
      setStatusMessage(
        'Please approve and create at least one test case before generating the risk-based execution plan.'
      )
      return
    }

    try {
      setActionType('Release Readiness')
      setStatus('Running')
      setIsGeneratingRiskPlan(true)
      setRiskPlanOutput(null)
      setExecutionReadinessOutput(null)
      setTestManagerWriteBackOutput(null)
      clearAutomationLinkState()
      setStatusMessage('Starting Risk-Based Test Planner job...')

      const result = await runRiskBasedTestPlannerAgent(
        uipathSDK,
        {
          requirementId: requirementId.trim(),
          submittedBy: submittedBy.trim(),
          environment,
          requirementTitle: agentOutput.requirementTitle,
          riskLevel: agentOutput.qaAnalysisSummary?.riskLevel,
          testingScope: agentOutput.qaAnalysisSummary?.testingScope,
          suggestedTestFocus: agentOutput.qaAnalysisSummary?.suggestedTestFocus,
          testScenarios: approvedScenarios as any,
          createdTestCases,
        },
        (message) => {
          setStatusMessage(message)
        }
      )

      setRiskPlanOutput(result.output ?? null)

      const plannerFailed = result.output?.planningStatus?.toLowerCase() === 'failed'
      const plannerError =
        result.output?.failedScenarios?.[0]?.errorMessage ||
        result.output?.failedScenarios?.[0]?.reason ||
        result.output?.failedScenarios?.[0]?.error ||
        ''

      if (plannerFailed) {
        setStatus('Error')
        setStatusMessage(`Risk planning failed: ${plannerError || 'Risk planner returned a failed status.'}`)
        return
      }

      if (result.jobState === 'Successful') {
        setStatus('Completed')
      } else {
        setStatus('Ready')
      }

      setStatusMessage(
        `${result.processingStatus} Job ID: ${result.jobId ?? 'N/A'}, State: ${
          result.jobState ?? 'N/A'
        }`
      )
    } catch (error) {
      setStatus('Error')
      setRiskPlanOutput(null)
      setTestManagerWriteBackOutput(null)
      clearAutomationLinkState()
      setStatusMessage(
        error instanceof Error
          ? error.message
          : 'Failed to generate risk-based execution plan.'
      )
    } finally {
      setIsGeneratingRiskPlan(false)
    }
  }

  const handleCheckExecutionReadiness = async () => {
    if (!generatedScenarios.length || !riskPlanOutput) {
      setStatus('Error')
      setStatusMessage(
        'Generate test scenarios and risk-based execution plan before checking execution readiness.'
      )
      return
    }

    if (!requirementId.trim() || !submittedBy.trim()) {
      setStatus('Error')
      setStatusMessage('Requirement ID and Submitted By are mandatory before execution readiness.')
      return
    }

    try {
      setActionType('Test Execution')
      setStatus('Running')
      setIsCheckingExecutionReadiness(true)
      setExecutionReadinessOutput(null)
      setTestManagerWriteBackOutput(null)
      clearAutomationLinkState()
      setStatusMessage('Starting Test Cloud Execution Readiness job...')

      const result = await runExecutionReadinessAgent(
        uipathSDK,
        {
          requirementId: requirementId.trim(),
          submittedBy: submittedBy.trim(),
          environment,
          requirementTitle: agentOutput?.requirementTitle,
          riskLevel: agentOutput?.qaAnalysisSummary?.riskLevel,
          qaReviewStatus: qaReviewDecision,
          testScenarioCount: generatedScenarios.length,
          adoTestCaseCreatedCount: testCaseWriteBackOutput?.createdTestCases?.length ?? 0,
          riskPlanningStatus: riskPlanOutput.planningStatus,
          recommendedExecutionOrder: riskPlanOutput.recommendedExecutionOrder,
          coverageSummary: riskPlanOutput.coverageSummary,
        },
        (message) => {
          setStatusMessage(message)
        }
      )

      setExecutionReadinessOutput(result.output ?? null)

      if (result.jobState === 'Successful') {
        setStatus('Completed')
      } else {
        setStatus('Ready')
      }

      setStatusMessage(
        `${result.processingStatus} Job ID: ${result.jobId ?? 'N/A'}, State: ${
          result.jobState ?? 'N/A'
        }`
      )
    } catch (error) {
      setStatus('Error')
      setExecutionReadinessOutput(null)
      setTestManagerWriteBackOutput(null)
      clearAutomationLinkState()
      setStatusMessage(
        error instanceof Error
          ? error.message
          : 'Failed to check execution readiness.'
      )
    } finally {
      setIsCheckingExecutionReadiness(false)
    }
  }

  const handleSyncTestManager = async () => {
    console.log('SYNC TO UIPATH TEST MANAGER BUTTON CLICKED')

    if (!generatedScenarios.length || !riskPlanOutput) {
      setStatus('Error')
      setStatusMessage(
        'Generate test scenarios and risk-based execution plan before syncing to UiPath Test Manager.'
      )
      return
    }

    if (!requirementId.trim() || !submittedBy.trim()) {
      setStatus('Error')
      setStatusMessage('Requirement ID and Submitted By are mandatory before Test Manager sync.')
      return
    }

    if (!TEST_MANAGER_PROJECT_KEY) {
      setStatus('Error')
      setStatusMessage(
        'UiPath Test Manager Project Key is missing. Please configure VITE_UIPATH_TEST_MANAGER_PROJECT_KEY.'
      )
      console.error('Missing VITE_UIPATH_TEST_MANAGER_PROJECT_KEY')
      return
    }

    const scenariosWithKeys = normalizeScenariosForReviewMemory(generatedScenarios)
    const approvedScenarios = scenariosWithKeys.filter(
      (scenario) => scenario.reviewStatus === 'Approved'
    )
    const createdAdoTestCases = testCaseWriteBackOutput?.createdTestCases || []

    if (!createdAdoTestCases.length) {
      setStatus('Error')
      setStatusMessage(
        'Please create approved Azure DevOps test cases before syncing to UiPath Test Manager.'
      )
      console.error('No created ADO test cases available for Test Manager sync')
      return
    }

    if (!approvedScenarios.length) {
      setStatus('Error')
      setStatusMessage('No approved scenarios available for UiPath Test Manager sync.')
      console.error('No approved scenarios available for Test Manager sync')
      return
    }

    const requirementTitle =
      agentOutput?.requirementTitle || `Requirement ${requirementId.trim()}`
    const requirementDescription =
      agentOutput?.requirementDescription ||
      `QualityOps generated requirement description for ${requirementTitle}. Testing scope: ${
        agentOutput?.qaAnalysisSummary?.testingScope?.join(', ') || 'generated QA scenarios'
      }.`

    try {
      setActionType('Test Execution')
      setStatus('Running')
      setIsSyncingTestManager(true)
      setTestManagerWriteBackOutput(null)
      clearAutomationLinkState()
      setStatusMessage('Starting UiPath Test Manager WriteBack job...')

      const payload = {
        requirementId: requirementId.trim(),
        submittedBy: submittedBy.trim(),
        environment,
        testManagerProjectKey: TEST_MANAGER_PROJECT_KEY,
        testManagerProjectName: TEST_MANAGER_PROJECT_KEY,
        requirementTitle,
        requirementDescription,
        riskLevel: agentOutput?.qaAnalysisSummary?.riskLevel,
        testScenarios: approvedScenarios as any,
        createdAdoTestCases,
        riskBasedPlan: riskPlanOutput,
        syncMode: 'RealSync',
        testSetMode: 'CreateOrReuseTestSet',
      }

      const result = await runTestManagerWriteBackAgent(
        uipathSDK,
        payload,
        (message) => {
          setStatusMessage(message)
        }
      )

      setTestManagerWriteBackOutput(result.output ?? null)

      if (result.output?.syncStatus === 'ConfigurationRequired') {
        setStatus('Ready')
      } else if (result.jobState === 'Successful') {
        setStatus('Completed')
      } else {
        setStatus('Ready')
      }

      setStatusMessage(
        `${result.processingStatus} Job ID: ${result.jobId ?? 'N/A'}, State: ${
          result.jobState ?? 'N/A'
        }`
      )
    } catch (error) {
      setStatus('Error')
      setTestManagerWriteBackOutput(null)
      clearAutomationLinkState()
      setStatusMessage(
        error instanceof Error
          ? error.message
          : 'Failed to prepare UiPath Test Manager sync.'
      )
    } finally {
      setIsSyncingTestManager(false)
    }
  }

  const handleMapAutomatedTestCases = async () => {
    if (!canMapAutomatedTestCases) {
      setAutomationLinkError('Run UiPath Test Manager Sync first to create UiPath Test Manager test cases.')
      return
    }

    try {
      setActionType('Test Execution')
      setStatus('Running')
      setAutomationLinkLoading(true)
      setAutomationLinkError('')
      setAutomationLinkResult(null)
      clearTriageState()
      setStatusMessage('Starting Automation Link job...')

      const scenarioEntryPointMap: Record<string, string> = {
        Functional: AUTOMATION_DEFAULT_ENTRY_POINT,
        Negative: AUTOMATION_DEFAULT_ENTRY_POINT,
        Integration: AUTOMATION_DEFAULT_ENTRY_POINT,
        Regression: AUTOMATION_DEFAULT_ENTRY_POINT,
      }
      const automationMappings = latestAutomationLinkTestCaseIds.map((testCaseId, index) => {
        const testCasePayload = testManagerWriteBackOutput?.testCasePayloads?.[index]
        const testType = testCasePayload?.testType || 'Functional'
        const entryPoint = scenarioEntryPointMap[testType] || AUTOMATION_DEFAULT_ENTRY_POINT

        return {
          testCaseId,
          scenarioId: testCasePayload?.scenarioId || '',
          packageIdentifier: AUTOMATION_LINK_PACKAGE_IDENTIFIER,
          entryPoint,
          simulatorProfile: entryPoint,
        }
      })

      console.log('Automation package identifier:', AUTOMATION_LINK_PACKAGE_IDENTIFIER)
      console.log('Automation default entry point:', AUTOMATION_DEFAULT_ENTRY_POINT)
      console.log('Automation mappings sent:', automationMappings)

      const result = await runAutomationLinkAgent(
        uipathSDK,
        {
          projectId: AUTOMATION_LINK_PROJECT_ID,
          createdTestCaseIds: latestAutomationLinkTestCaseIds,
          packageIdentifier: AUTOMATION_LINK_PACKAGE_IDENTIFIER,
          automationMappings,
        },
        (message) => {
          setStatusMessage(sanitizeUserFacingText(message))
        }
      )

      setAutomationLinkResult(result.output ?? null)

      if (result.jobState === 'Successful') {
        setStatus('Completed')
      } else {
        setStatus('Ready')
      }

      setStatusMessage(
        result.jobState === 'Successful'
          ? 'Automation Mapping Completed'
          : sanitizeUserFacingText(
              `${result.processingStatus} Job ID: ${result.jobId ?? 'N/A'}, State: ${
                result.jobState ?? 'N/A'
              }`
            )
      )
    } catch (error) {
      const errorMessage = sanitizeUserFacingText(
        error instanceof Error
          ? error.message
          : 'Failed to map automated test cases.'
      )

      setStatus('Error')
      setAutomationLinkResult(null)
      setAutomationLinkError(errorMessage)
      setStatusMessage(errorMessage)
    } finally {
      setAutomationLinkLoading(false)
    }
  }

  const handleLoadTestExecutions = async () => {
    if (!automationMappingCompleted) {
      setTriageMessage('Complete automation mapping before analyzing test results.')
      return
    }

    try {
      setActionType('Test Execution')
      setStatus('Running')
      setTriageLoadingExecutions(true)
      setTriageError('')
      setTriageMessage('')
      setTriageExecutions([])
      setSelectedExecution(null)
      setTriageAnalysisResult(null)
      setSelectedTriageResultKeys([])
      setTriageClassificationOverrides({})
      setDefectCreationResults([])
      setFinalReportGeneratedAt('')
      setStatusMessage('Loading Test Manager executions...')

      const result = await runTestResultTriageAgent(
        uipathSDK,
        {
          mode: 'listExecutions',
          projectId: AUTOMATION_LINK_PROJECT_ID,
        },
        (message) => {
          setStatusMessage(sanitizeUserFacingText(message))
        }
      )

      if (result.output?.status?.toLowerCase() === 'error') {
        const errorMessage = getTriageErrorMessage(result.output)

        setStatus('Error')
        setTriageError(errorMessage)
        setTriageMessage('')
        setStatusMessage(errorMessage)
        return
      }

      const executions = getTriageExecutions(result.output)
      const executionTotal = getTriageExecutionTotal(result.output, executions)
      setTriageExecutions(executions)
      setTriageMessage(
        executions.length
          ? `${executionTotal} Test Manager executions found.`
          : 'No Test Manager executions found.'
      )
      setStatus(result.jobState === 'Successful' ? 'Completed' : 'Ready')
      setStatusMessage(
        sanitizeUserFacingText(
          `${result.processingStatus} Job ID: ${result.jobId ?? 'N/A'}, State: ${
            result.jobState ?? 'N/A'
          }`
        )
      )
    } catch (error) {
      const errorMessage = sanitizeUserFacingText(
        error instanceof Error ? error.message : 'Failed to load Test Manager executions.'
      )

      setStatus('Error')
      setTriageError(errorMessage)
      setTriageMessage('')
      setStatusMessage(errorMessage)
    } finally {
      setTriageLoadingExecutions(false)
    }
  }

  const handleAnalyzeTestResults = async () => {
    if (!selectedExecution?.testExecutionId) {
      setTriageError('Select a Test Manager execution before analysis.')
      return
    }

    try {
      setActionType('Test Execution')
      setStatus('Running')
      setTriageAnalyzing(true)
      setTriageError('')
      setTriageMessage('')
      setTriageAnalysisResult(null)
      setSelectedTriageResultKeys([])
      setExpandedTriageResultKeys([])
      setTriageClassificationOverrides({})
      setDefectCreationResults([])
      setFinalReportGeneratedAt('')
      setStatusMessage('Analyzing failed test results...')

      const result = await runTestResultTriageAgent(
        uipathSDK,
        {
          mode: 'analyzeExecution',
          projectId: AUTOMATION_LINK_PROJECT_ID,
          testExecutionId: String(selectedExecution.testExecutionId),
        },
        (message) => {
          setStatusMessage(sanitizeUserFacingText(message))
        }
      )

      const output = result.output ?? null
      const nextOverrides: Record<string, string> = {}
      const outputStatus = (output?.status || '').toLowerCase()
      const nestedOutputStatus = (output?.result?.status || '').toLowerCase()

      if (outputStatus === 'error' || nestedOutputStatus === 'error') {
        const errorMessage = getTriageErrorMessage(output)
        setStatus('Error')
        setTriageAnalysisResult(output)
        setTriageError(errorMessage)
        setTriageMessage('')
        setStatusMessage(errorMessage)
        return
      }

      const outputTriageResults = getTriageResults(output)

      outputTriageResults.forEach((triageResult, index) => {
        nextOverrides[getTriageResultKey(triageResult, index)] = getDisplayClassification(
          triageResult
        )
      })

      setTriageAnalysisResult(output)
      setTriageClassificationOverrides(nextOverrides)
      setTriageMessage(
        outputTriageResults.length
          ? sanitizeUserFacingText(
              getTriageOverallRecommendation(output) || 'Review failed test results.'
            )
          : 'No failed test results found for this execution.'
      )
      setStatus(result.jobState === 'Successful' ? 'Completed' : 'Ready')
      setStatusMessage(
        sanitizeUserFacingText(
          `${result.processingStatus} Job ID: ${result.jobId ?? 'N/A'}, State: ${
            result.jobState ?? 'N/A'
          }`
        )
      )
    } catch (error) {
      const errorMessage = sanitizeUserFacingText(
        error instanceof Error ? error.message : 'Failed to analyze test results.'
      )

      setStatus('Error')
      setTriageAnalysisResult(null)
      setTriageError(errorMessage)
      setTriageMessage('')
      setStatusMessage(errorMessage)
    } finally {
      setTriageAnalyzing(false)
    }
  }

  const handleCreateDefects = async () => {
    const parentStoryId = adoParentStoryId.trim()

    if (!selectedExecution?.testExecutionId || !hasSelectedFailedResults || !parentStoryId) {
      return
    }

    try {
      setActionType('Test Execution')
      setStatus('Running')
      setTriageCreatingDefects(true)
      setTriageError('')
      setTriageMessage('')
      setDefectCreationResults([])
      setFinalReportGeneratedAt('')
      setStatusMessage('Creating Azure DevOps bugs for selected failed results...')

      const selectedResults = failedTriageResults
        .map((triageResult, index) => ({
          key: getTriageResultKey(triageResult, index),
          triageResult,
        }))
        .filter((item) => selectedTriageResultKeys.includes(item.key))

      const createdResults: DefectCreationResult[] = []

      for (const item of selectedResults) {
        const currentClassification =
          triageClassificationOverrides[item.key] ||
          getDisplayClassification(item.triageResult)

        const result = await runTestResultTriageAgent(
          uipathSDK,
          {
            mode: 'createDefect',
            projectId: AUTOMATION_LINK_PROJECT_ID,
            adoParentId: parentStoryId,
            testExecutionId: String(selectedExecution.testExecutionId),
            testCaseId: item.triageResult.testCaseId || '',
            testCaseName: item.triageResult.testCaseName || item.triageResult.testCaseId || '',
            linkToTestCaseLog: item.triageResult.linkToTestCaseLog || '',
            classification: currentClassification,
            evidence: item.triageResult.evidence || '',
            recommendedAction: item.triageResult.recommendedAction || '',
          },
          (message) => {
            setStatusMessage(sanitizeUserFacingText(message))
          }
        )

        const output = result.output
        const defectStatus = output?.defectSyncStatus || output?.defectCreationStatus || ''
        const blockedReasons = output?.blockedReasons ?? output?.result?.blockedReasons
        const outputStatus = (output?.status || output?.result?.status || '').toLowerCase()
        const backendMessage =
          output?.message ||
          output?.result?.message ||
          (blockedReasons?.length ? blockedReasons.join(' ') : '') ||
          output?.nextAction ||
          result.processingStatus
        const statusClass =
          outputStatus === 'error' || blockedReasons?.length
            ? 'not-ready'
            : getDefectStatusClass(defectStatus || output?.status)

        createdResults.push({
          testCaseId: item.triageResult.testCaseId || item.key,
          status:
            statusClass === 'not-ready'
              ? 'Failed'
              : statusClass === 'warning'
                ? 'InProgress'
                : 'Completed',
          output,
          classification: currentClassification,
          testManagerEvidenceLink: item.triageResult.linkToTestCaseLog || '',
          message: sanitizeUserFacingText(backendMessage || 'Azure DevOps bug request completed.'),
        })
      }

      setDefectCreationResults(createdResults)
      setTriageMessage('Azure DevOps bug creation requests completed.')
      setStatus(createdResults.some((item) => item.status === 'Failed') ? 'Ready' : 'Completed')
      setStatusMessage('Azure DevOps bug creation requests completed.')
    } catch (error) {
      const errorMessage = sanitizeUserFacingText(
        error instanceof Error ? error.message : 'Azure DevOps bug creation failed.'
      )

      setStatus('Error')
      setTriageError(errorMessage)
      setStatusMessage(errorMessage)
    } finally {
      setTriageCreatingDefects(false)
    }
  }

  const handleClear = () => {
    setActionType('Requirement Analysis')
    setRequirementId('')
    setSubmittedBy('')
    setEnvironment('SQA')
    setStatus('Idle')
    setStatusMessage('Select an action and provide the required details to start.')
    setAgentOutput(null)
    clearTestGenerationState()
    setTestCaseWriteBackOutput(null)
    setRiskPlanOutput(null)
    setExecutionReadinessOutput(null)
    setTestManagerWriteBackOutput(null)
    clearAutomationLinkState()
    clearTriageState()
    setAdoParentStoryId('')
    setQaLeadDecision('')
    setQaReviewDecision('Pending')
    setDecisionStatus('Idle')
    clearMemoryFeedbackState()
    setIsCreatingTestCases(false)
    setIsGeneratingRiskPlan(false)
    setIsCheckingExecutionReadiness(false)
    setIsSyncingTestManager(false)
  }

  const workflowRunner = (
    <div className="qo-runner-card">
      <div className="panel-header">
        <h3>Workflow Runner</h3>
        <p>Select an action and provide input details.</p>
      </div>

      <div className="qo-runner-form">
        <label className="qo-runner-field">
          Action Type
          <select value={actionType} onChange={(event) => setActionType(event.target.value as QaAction)}>
            <option>Requirement Analysis</option>
            <option>Test Generation</option>
            <option>Test Execution</option>
            <option>Requirement Review</option>
            <option>Release Readiness</option>
          </select>
        </label>

        <label className="qo-runner-field">
          Environment
          <select value={environment} onChange={(event) => setEnvironment(event.target.value)}>
            <option>DEV</option>
            <option>SQA</option>
            <option>UAT</option>
            <option>Production</option>
          </select>
        </label>

        <label className="qo-runner-field">
          Requirement ID <span>*</span>
          <input
            value={requirementId}
            onChange={(event) => setRequirementId(event.target.value)}
            placeholder="Enter requirement ID"
          />
        </label>

        <label className="qo-runner-field">
          Submitted By <span>*</span>
          <input
            value={submittedBy}
            onChange={(event) => setSubmittedBy(event.target.value)}
            placeholder="Enter submitter name"
          />
        </label>
      </div>

      <div className="qo-runner-actions">
        <button className="primary-button primary" onClick={handleRun} disabled={status === 'Running'}>
          {status === 'Running' ? 'Running...' : 'Run Selected QA Action'}
        </button>

        <button className="secondary-button secondary" onClick={handleClear}>
          Clear
        </button>
      </div>
    </div>
  )

  const requirementAnalysisContent = agentOutput ? (
    <section className="dashboard-card requirement-analysis-section">
      <div className="section-header">
        <div>
          <span className="small-label">Live Agent Result</span>
          <h3>Requirement Analysis Output</h3>
        </div>

        <span className="score-pill">
          Score {agentOutput.requirementQualityAnalysis?.readinessScore ?? '-'}
        </span>
      </div>

      <div className="summary-grid analysis-summary-grid">
        <div className="summary-item">
          <span>Readiness</span>
          <strong>{agentOutput.requirementQualityAnalysis?.readinessStatus || '-'}</strong>
        </div>

        <div className="summary-item">
          <span>Risk</span>
          <strong>{agentOutput.qaAnalysisSummary?.riskLevel || '-'}</strong>
        </div>

        <div className="summary-item">
          <span>Recommendation</span>
          <strong>{agentOutput.requirementQualityAnalysis?.approvalRecommendation || '-'}</strong>
        </div>
      </div>

      <div className="analysis-detail-grid">
        <div className="output-section">
          <span>Requirement Title</span>
          <p>{agentOutput.requirementTitle || '-'}</p>
        </div>

        <div className="output-section">
          <span>Next Step</span>
          <p>{agentOutput.qaAnalysisSummary?.nextStep || '-'}</p>
        </div>

        <div className="output-section">
          <span>Testing Scope</span>
          {agentOutput.qaAnalysisSummary?.testingScope?.length ? (
            <ul className="compact-list">
              {agentOutput.qaAnalysisSummary.testingScope.map((item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              ))}
            </ul>
          ) : (
            <p>-</p>
          )}
        </div>

        <div className="output-section">
          <span>Suggested Test Focus</span>
          {cleanSuggestedTestFocus.length ? (
            <ul className="analysis-list">
              {cleanSuggestedTestFocus.map((item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              ))}
            </ul>
          ) : (
            <p>-</p>
          )}
        </div>
      </div>

      <div className="output-section">
        <span>Identified Gaps</span>
        {cleanIdentifiedGaps.length ? (
          <ul className="analysis-list">
            {cleanIdentifiedGaps.map((gap, index) => (
              <li key={`${gap}-${index}`}>{gap}</li>
            ))}
          </ul>
        ) : (
          <p>No gaps identified.</p>
        )}
      </div>

      <details className="details-section">
        <summary>View requirement details</summary>

        <div className="analysis-detail-grid">
          <div className="output-section">
            <span>Description</span>
            <p>{agentOutput.requirementDescription || '-'}</p>
          </div>

          <div className="output-section">
            <span>Acceptance Criteria</span>
            <p>{agentOutput.acceptanceCriteria || '-'}</p>
          </div>
        </div>
      </details>
    </section>
  ) : (
    <section className="empty-state-card">
      <h3>Requirement Analysis Output</h3>
      <p>Run Requirement Analysis from the Dashboard to populate this section.</p>
    </section>
  )

  const requirementReviewContent = (
    <section className="dashboard-card qa-review-section">
      <div className="section-header">
        <div>
          <span className="small-label">QA Lead Decision Stage</span>
          <h3>Requirement Review</h3>
          <p>
            Review requirement analysis, risk assessment, missing information, and QA readiness
            before test generation.
          </p>
        </div>
      </div>

      <div className="memory-feedback-section">
        <div className="section-header compact-section-header">
          <div>
            <span className="small-label">Workflow Memory</span>
            <h4>QA Lead Review</h4>
          </div>
        </div>

        <p className="readiness-helper">
          QualityOps uses workflow memory by passing QA Lead review feedback through the input
          schema to downstream agents. This keeps the human review decision available during test
          generation.
        </p>

        <div className="memory-feedback-summary-grid">
          <div className="summary-item">
            <span>Requirement ID</span>
            <strong>{renderTechnicalText(requirementId || '-')}</strong>
          </div>
          <div className="summary-item">
            <span>Readiness Status</span>
            <strong>
              {renderTechnicalText(
                agentOutput?.requirementQualityAnalysis?.readinessStatus || '-'
              )}
            </strong>
          </div>
          <div className="summary-item">
            <span>Readiness Score</span>
            <strong>{agentOutput?.requirementQualityAnalysis?.readinessScore ?? '-'}</strong>
          </div>
          <div className="summary-item">
            <span>Risk Level</span>
            <strong>{renderTechnicalText(agentOutput?.qaAnalysisSummary?.riskLevel || '-')}</strong>
          </div>
          <div className="summary-item requirement-title-card">
            <span>Requirement Title</span>
            <strong>{renderTechnicalText(agentOutput?.requirementTitle || '-')}</strong>
          </div>
        </div>

        <div className="memory-feedback-detail-grid">
          <div className="output-section">
            <span>Identified Gaps</span>
            {cleanIdentifiedGaps.length ? (
              <ul className="analysis-list">
                {cleanIdentifiedGaps.map((gap, index) => (
                  <li key={`${gap}-${index}`}>{gap}</li>
                ))}
              </ul>
            ) : (
              <p>No gaps identified.</p>
            )}
          </div>
          <div className="output-section">
            <span>Suggested Test Focus</span>
            {cleanSuggestedTestFocus.length ? (
              <ul className="analysis-list">
                {cleanSuggestedTestFocus.map((focus, index) => (
                  <li key={`${focus}-${index}`}>{focus}</li>
                ))}
              </ul>
            ) : (
              <p>No suggested test focus returned.</p>
            )}
          </div>
        </div>

        <div className="memory-feedback-form-grid">
          <label>
            QA Lead Decision <span>*</span>
            <select
              value={memoryFeedbackDecision}
              onChange={(event) =>
                setMemoryFeedbackDecision(event.target.value as MemoryFeedbackDecision)
              }
            >
              <option value="">Select decision</option>
              <option value="Approve">Approve</option>
              <option value="Needs Changes">Needs Changes</option>
              <option value="Reject">Reject</option>
            </select>
          </label>

          <label>
            Feedback Category <span>*</span>
            <select
              value={memoryFeedbackCategory}
              onChange={(event) =>
                setMemoryFeedbackCategory(event.target.value as MemoryFeedbackCategory)
              }
            >
              <option value="">Select category</option>
              <option value="Risk correction">Risk correction</option>
              <option value="Missing gap">Missing gap</option>
              <option value="Test focus improvement">Test focus improvement</option>
              <option value="Readiness score correction">Readiness score correction</option>
              <option value="Approval decision correction">Approval decision correction</option>
              <option value="General feedback">General feedback</option>
            </select>
          </label>

          <label className="memory-feedback-text-field">
            Feedback
            {['Needs Changes', 'Reject'].includes(memoryFeedbackDecision) && (
              <span className="field-helper">
                Feedback is required when the requirement needs changes or is rejected.
              </span>
            )}
            <textarea
              value={memoryFeedbackText}
              onChange={(event) => setMemoryFeedbackText(event.target.value)}
              placeholder="Add QA Lead feedback. This feedback will be passed to downstream QualityOps agents."
              rows={6}
            />
          </label>
        </div>

        <div className="qa-lead-actions">
          <button
            className="approve-button"
            onClick={handleSaveQaLeadReview}
            disabled={decisionStatus === 'Updating' || qaLeadReviewSaving}
          >
            {qaLeadReviewSaving ? 'Saving QA Lead Review...' : 'Save QA Lead Review'}
          </button>

          <button
            className="generate-button"
            onClick={handleGenerateTests}
            disabled={
              !agentOutput ||
              decisionStatus === 'Updating' ||
              status === 'Running' ||
              qaReviewDecision !== 'Approved'
            }
          >
            {status === 'Running' && actionType === 'Test Generation'
              ? 'Generating...'
              : 'Generate Test Scenarios'}
          </button>
        </div>

        {qaLeadReview && (
          <div className="qa-lead-review-memory-card">
            <div className="report-card-header">
              <span className="scenario-section-label">QA Lead Review Memory</span>
              <strong>
                {qaLeadReview.decision === 'Approve'
                  ? 'Approved for Test Generation'
                  : 'Clarification Required'}
              </strong>
              {adoCommentAdded && (
                <span className="readiness-status-badge ready">ADO Comment Added</span>
              )}
            </div>
            <div className="memory-feedback-summary-grid">
              <div className="summary-item">
                <span>Decision</span>
                <strong>{qaLeadReview.decision}</strong>
              </div>
              <div className="summary-item">
                <span>Feedback Category</span>
                <strong>{qaLeadReview.feedbackCategory}</strong>
              </div>
              <div className="summary-item">
                <span>Submitted By</span>
                <strong>{qaLeadReview.submittedBy}</strong>
              </div>
              <div className="summary-item">
                <span>Created At</span>
                <strong>{qaLeadReview.createdAt}</strong>
              </div>
            </div>
            <div className="output-section">
              <span>Feedback</span>
              <p>{qaLeadReview.feedbackText}</p>
            </div>
            {qaLeadReview.decision !== 'Approve' && (
              <p className="readiness-helper">
                Requirement requires clarification before test generation.
              </p>
            )}
          </div>
        )}

        {memoryFeedbackMessage && (
          <div className={`result-box ${qaLeadReviewSaving ? 'running' : 'completed'} memory-feedback-status`}>
            <strong>QA Lead Review Memory</strong>
            <p>{memoryFeedbackMessage}</p>
          </div>
        )}

        {memoryFeedbackError && (
          <div className="result-box error memory-feedback-status">
            <strong>QA Lead Review Memory</strong>
            <p>{memoryFeedbackError}</p>
          </div>
        )}
      </div>

      <div className={`decision-status-panel ${decisionStatus.toLowerCase()}`}>
        <strong>Requirement Review Status: {decisionStatus}</strong>
        <p>{qaLeadDecision || 'No requirement review decision has been submitted yet.'}</p>
      </div>
    </section>
  )

  const testGenerationMetadataItems = testGenerationResult
    ? [
        { label: 'Generation Mode', value: testGenerationResult.generationMode },
        { label: 'LLM Generation Used', value: testGenerationResult.llmGenerationUsed },
        { label: 'Vector RAG Status', value: testGenerationResult.vectorRagStatus },
        { label: 'Fallback RAG Used', value: testGenerationResult.fallbackRagUsed },
        { label: 'RAG Sources Used', value: testGenerationResult.ragSourcesUsed },
      ]
        .map((item) => ({
          ...item,
          displayValue: formatTestGenerationMetadataValue(item.value),
        }))
        .filter((item) => item.displayValue)
    : []

  const testCaseReviewCounts = getReviewCounts()

  const testGenerationContent = (
    <section className="dashboard-card test-generation-section">
      <div className="section-header">
        <div>
          <span className="small-label">Generated QA Artifact</span>
          <h3>Generated Test Scenarios</h3>
          <p>Structured QA scenarios generated from requirement risk, scope, and test focus.</p>
        </div>

        {testGenerationResult && (
          <div className="test-scenario-meta">
            <span className="scenario-status-badge">
              {testGenerationResult.generationStatus || 'Generated'}
            </span>
            <span className="scenario-count-badge">
              {generatedScenarios.length} scenarios
            </span>
          </div>
        )}
      </div>

      {testGenerationMetadataItems.length > 0 && (
        <div className="test-generation-metadata-grid">
          {testGenerationMetadataItems.map((item) => (
            <div className="summary-item" key={item.label}>
              <span>{item.label}</span>
              <strong>{renderTechnicalText(item.displayValue)}</strong>
            </div>
          ))}
        </div>
      )}

      <div className="qa-lead-review-memory-card">
        <div className="report-card-header">
          <span className="scenario-section-label">QA Lead Review Memory</span>
          <strong>
            {qaLeadReview
              ? qaLeadReview.decision === 'Approve'
                ? 'Approved for Test Generation'
                : 'Clarification Required'
              : 'Not Available'}
          </strong>
        </div>

        {qaLeadReview ? (
          <div className="memory-feedback-summary-grid">
            <div className="summary-item">
              <span>Decision</span>
              <strong>{qaLeadReview.decision}</strong>
            </div>
            <div className="summary-item">
              <span>Feedback Category</span>
              <strong>{qaLeadReview.feedbackCategory}</strong>
            </div>
            <div className="summary-item">
              <span>Created At</span>
              <strong>{qaLeadReview.createdAt}</strong>
            </div>
            <div className="summary-item final-recommendation-item">
              <span>Feedback</span>
              <strong>{qaLeadReview.feedbackText}</strong>
            </div>
          </div>
        ) : (
          <p className="readiness-helper">
            No QA Lead review memory found. Please complete Requirement Review before generating
            test scenarios.
          </p>
        )}
      </div>

      <div className="section-action-row">
        <button
          className="generate-button"
          onClick={handleGenerateTests}
          disabled={
            !agentOutput ||
            decisionStatus === 'Updating' ||
            status === 'Running' ||
            qaReviewDecision !== 'Approved'
          }
        >
          {status === 'Running' && actionType === 'Test Generation'
            ? 'Generating...'
            : 'Generate Test Scenarios'}
        </button>
      </div>

      {generatedScenarios.length > 0 && (
        <div className="qa-lead-review-memory-card">
          <div className="report-card-header">
            <span className="scenario-section-label">Test Case Review Gate</span>
            <strong>Approve generated scenarios before Azure DevOps creation</strong>
          </div>
          <p className="readiness-helper">{reviewMemorySyncStatus}</p>
          <div className="memory-feedback-summary-grid">
            <div className="summary-item">
              <span>Total Generated</span>
              <strong>{testCaseReviewCounts.total}</strong>
            </div>
            <div className="summary-item">
              <span>Approved</span>
              <strong>{testCaseReviewCounts.approved}</strong>
            </div>
            <div className="summary-item">
              <span>Rejected</span>
              <strong>{testCaseReviewCounts.rejected}</strong>
            </div>
            <div className="summary-item">
              <span>Pending</span>
              <strong>{testCaseReviewCounts.pending}</strong>
            </div>
          </div>
          <div className="section-action-row">
            <button className="approve-button" onClick={() => updateAllScenarioReviewStatuses('Approved')}>
              Approve All
            </button>
            <button className="clarify-button" onClick={() => updateAllScenarioReviewStatuses('Rejected')}>
              Reject All
            </button>
            <button className="secondary-button" onClick={() => updateAllScenarioReviewStatuses('Pending')}>
              Reset Review
            </button>
            {/* TODO: remove after memory sync verification */}
            <button
              className="secondary-button"
              onClick={() => {
                const scenariosWithKeys = normalizeScenariosForReviewMemory(generatedScenarios)
                console.log('Test Memory Sync clicked', {
                  requirementId: requirementId.trim() || 'latest',
                  count: scenariosWithKeys.length,
                })
                void saveReviewMemoryToDataService(
                  uipathSDK,
                  requirementId.trim() || 'latest',
                  scenariosWithKeys
                )
                  .then((result) => {
                    console.log('Test Memory Sync success', result)
                  })
                  .catch((error) => {
                    console.error('Test Memory Sync failed', error)
                  })
              }}
            >
              Test Memory Sync
            </button>
          </div>
        </div>
      )}

      {generatedScenarios.length > 0 ? (
        <div className="test-scenario-list">
          {generatedScenarios.map((scenario, index) => (
            <article className="test-scenario-item" key={`${scenario.scenarioId || 'scenario'}-${index}`}>
              <div className="test-scenario-header">
                <div>
                  <span className="scenario-id">{scenario.scenarioId || `TS-${index + 1}`}</span>
                  <strong>{getScenarioTitle(scenario, index)}</strong>
                </div>

                <div className="scenario-badge-row">
                  <span className="scenario-status-badge">
                    {scenario.reviewStatus === 'Pending' ? 'Pending Review' : scenario.reviewStatus}
                  </span>
                  <span className="scenario-priority">{scenario.priority || 'Priority N/A'}</span>
                  <span className="scenario-type-badge">{scenario.testType || 'Type N/A'}</span>
                </div>
              </div>

              <div className="scenario-section">
                <span className="scenario-section-label">QA Lead Review</span>
                <div className="section-action-row">
                  <button
                    className="approve-button"
                    onClick={() => {
                      console.log('APPROVE BUTTON CLICKED')
                      console.log('Calling Memory Agent SAVE_REVIEW_MEMORY from Approve')
                      updateScenarioReviewStatus(index, 'Approved')
                    }}
                  >
                    Approve
                  </button>
                  <button
                    className="clarify-button"
                    onClick={() => {
                      console.log('REJECT BUTTON CLICKED')
                      console.log('Calling Memory Agent SAVE_REVIEW_MEMORY from Reject')
                      updateScenarioReviewStatus(index, 'Rejected')
                    }}
                  >
                    Reject
                  </button>
                  {editingScenarioIndex === index ? (
                    <>
                      <button className="approve-button" onClick={() => saveScenarioEdit(index)}>
                        Save Edit
                      </button>
                      <button className="secondary-button" onClick={() => cancelScenarioEdit(index)}>
                        Cancel Edit
                      </button>
                    </>
                  ) : (
                    <button className="secondary-button" onClick={() => startEditingScenario(scenario, index)}>
                      Edit
                    </button>
                  )}
                </div>
                <label className="memory-feedback-text-field">
                  <textarea
                    value={scenario.reviewComment}
                    onChange={(event) => updateScenarioReviewComment(index, event.target.value)}
                    placeholder="Add review comment..."
                    rows={3}
                  />
                </label>
                {scenario.reviewedAt && (
                  <p className="readiness-helper">
                    Reviewed by {scenario.reviewedBy || 'QA Lead'} at {scenario.reviewedAt}
                  </p>
                )}
              </div>

              {editingScenarioIndex === index && scenarioEditDrafts[index] && (
                <div className="scenario-section">
                  <span className="scenario-section-label">Edit Scenario</span>
                  <label className="memory-feedback-text-field">
                    <span>Title</span>
                    <textarea
                      value={scenarioEditDrafts[index].title || ''}
                      onChange={(event) =>
                        updateScenarioEditDraft(index, (draft) => ({
                          ...draft,
                          title: event.target.value,
                        }))
                      }
                      rows={2}
                    />
                  </label>
                  <label className="memory-feedback-text-field">
                    <span>Description</span>
                    <textarea
                      value={scenarioEditDrafts[index].description || ''}
                      onChange={(event) =>
                        updateScenarioEditDraft(index, (draft) => ({
                          ...draft,
                          description: event.target.value,
                        }))
                      }
                      rows={3}
                    />
                  </label>
                  {Array.isArray(scenarioEditDrafts[index].steps) &&
                    scenarioEditDrafts[index].steps?.map((step, stepIndex) => {
                      const normalizedStep = normalizeStepForEdit(step)

                      return (
                        <div className="output-section" key={`edit-step-${stepIndex}`}>
                          <span>Step {stepIndex + 1}</span>
                          <label className="memory-feedback-text-field">
                            <span>Action</span>
                            <textarea
                              value={normalizedStep.action}
                              onChange={(event) =>
                                updateScenarioEditStep(index, stepIndex, 'action', event.target.value)
                              }
                              rows={2}
                            />
                          </label>
                          <label className="memory-feedback-text-field">
                            <span>Expected Result</span>
                            <textarea
                              value={normalizedStep.expectedResult}
                              onChange={(event) =>
                                updateScenarioEditStep(
                                  index,
                                  stepIndex,
                                  'expectedResult',
                                  event.target.value
                                )
                              }
                              rows={2}
                            />
                          </label>
                        </div>
                      )
                    })}
                </div>
              )}

              <div className="scenario-section">
                <span className="scenario-section-label">Preconditions</span>
                {scenario.preconditions?.length ? (
                  <ul className="scenario-preconditions">
                    {scenario.preconditions.map((precondition, preconditionIndex) => (
                      <li key={`${precondition}-${preconditionIndex}`}>{precondition}</li>
                    ))}
                  </ul>
                ) : (
                  <p>-</p>
                )}
              </div>

              <div className="scenario-section">
                <span className="scenario-section-label">Steps</span>
                {Array.isArray(scenario.steps) && scenario.steps.length > 0 ? (
                  <ol className="scenario-steps">
                    {scenario.steps.map((step: any, stepIndex: number) => (
                      <li key={stepIndex}>
                        {renderTestStep(step)}
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p>-</p>
                )}
              </div>

              <div className="scenario-section expected-result">
                <span className="scenario-section-label">Expected Result</span>
                <p>{scenario.expectedResult || '-'}</p>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p className="empty-scenarios">No test scenarios were returned yet.</p>
      )}
    </section>
  )

  const canCheckExecutionReadiness =
    Boolean(generatedScenarios.length) && Boolean(riskPlanOutput)

  const canSyncTestManager =
    Boolean(generatedScenarios.length) && Boolean(riskPlanOutput)

  const testManagerSyncStatusClass =
    testManagerWriteBackOutput?.syncStatus === 'Completed'
      ? 'ready'
      : ['ConfigurationRequired', 'ReadyToSync'].includes(
          testManagerWriteBackOutput?.syncStatus || ''
        )
        ? 'warning'
      : 'not-ready'

  const testManagerSyncStatusLabel =
    testManagerWriteBackOutput?.syncStatus === 'ConfigurationRequired'
      ? 'Configuration Required'
      : testManagerWriteBackOutput?.syncStatus || 'Pending'

  const generatedScenarioCount = generatedScenarios.length
  const adoTestCaseCount = testCaseWriteBackOutput?.createdTestCases?.length ?? 0
  const requirementAnalysisSummaryStatus = isRequirementAnalysisCompleted ? 'Completed' : 'Pending'
  const riskPlanSummaryStatus = isRiskPlanCompleted ? 'Completed' : 'Pending'
  const testManagerSyncSummaryStatus = testManagerWriteBackOutput?.syncStatus || 'Pending'
  const executionReadinessCheckReady = isExecutionReadinessCompleted
  const testManagerSyncCompleted = isTestManagerSyncCompleted
  const allMandatoryReadinessStepsComplete =
    requirementAnalysisSummaryStatus === 'Completed' &&
    isRequirementReviewCompleted &&
    isTestGenerationCompleted &&
    adoTestCaseCount > 0 &&
    riskPlanSummaryStatus === 'Completed' &&
    executionReadinessCheckReady &&
    testManagerSyncCompleted
  const workflowReadinessStatus = allMandatoryReadinessStepsComplete ? 'Ready' : 'Action Required'
  const workflowReadinessBadgeClass = allMandatoryReadinessStepsComplete ? 'ready' : 'warning'
  const executionReadinessSummaryStatus = executionReadinessCheckReady && testManagerSyncCompleted
    ? 'Ready'
    : 'Pending'
  const finalRecommendation = adoTestCaseCount === 0
    ? 'Create approved test cases in Azure DevOps before readiness check.'
    : riskPlanSummaryStatus !== 'Completed'
      ? 'Generate risk-based execution plan before readiness check.'
      : !testManagerSyncCompleted
        ? 'Complete UiPath Test Manager Sync before execution.'
        : allMandatoryReadinessStepsComplete
          ? 'QA workflow is ready for execution.'
          : 'Complete pending QA workflow steps before execution.'
  const finalReportEmailSent = Boolean(finalReportEmailResult) && !finalReportEmailError
  const getExecutionStepStatusClass = (stepStatus: ExecutionStepStatus) =>
    stepStatus.toLowerCase().replace(/\s+/g, '-')
  const adoTestCaseStepStatus: ExecutionStepStatus = testCaseWriteBackOutput?.createdTestCases?.length
    ? 'Completed'
    : isCreatingTestCases
      ? 'Ready'
      : generatedScenarios.length
        ? 'Ready'
        : 'Pending'
  const testManagerSyncStepStatus: ExecutionStepStatus =
    testManagerWriteBackOutput?.syncStatus === 'Completed'
      ? 'Completed'
      : testManagerWriteBackOutput?.syncStatus === 'ConfigurationRequired'
        ? 'Needs Attention'
        : testManagerWriteBackOutput?.syncStatus === 'ReadyToSync'
          ? 'Needs Attention'
          : canSyncTestManager
            ? 'Ready'
            : 'Pending'
  const automationMappingStepStatus: ExecutionStepStatus = automationLinkError
    ? 'Failed'
    : automationLinkResult
      ? 'Completed'
      : canMapAutomatedTestCases
        ? 'Ready'
        : 'Pending'
  const manualExecutionStepStatus: ExecutionStepStatus = selectedExecution
    ? 'Completed'
    : automationMappingCompleted
      ? 'Ready'
      : 'Pending'
  const triageStepStatus: ExecutionStepStatus = triageError
    ? 'Failed'
    : triageAnalysisResult
      ? 'Completed'
      : automationMappingCompleted
        ? 'Ready'
        : 'Pending'
  const defectCreationStepStatus: ExecutionStepStatus = defectCreationResults.some(
    (item) => item.status === 'Failed'
  )
    ? 'Failed'
    : defectCreationResults.length > 0
      ? 'Completed'
      : canCreateAdoBug
        ? 'Ready'
        : 'Pending'
  const finalReportStepStatus: ExecutionStepStatus = finalReportGeneratedAt
    ? 'Completed'
    : triageAnalysisResult
      ? 'Ready'
      : 'Pending'
  const emailStepStatus: ExecutionStepStatus = finalReportEmailError
    ? 'Failed'
    : finalReportEmailSent
      ? 'Completed'
      : finalReportGeneratedAt
        ? 'Ready'
        : 'Pending'
  const renderExecutionStepHeader = (
    stepNumber: number,
    title: string,
    description: string,
    stepStatus: ExecutionStepStatus
  ) => (
    <div className="execution-step-header">
      <div className="execution-step-title-row">
        <span className="execution-step-number">{stepNumber}</span>
        <div>
          <h3>{title}</h3>
          <p>{description}</p>
        </div>
      </div>
      <span className={`execution-step-status ${getExecutionStepStatusClass(stepStatus)}`}>
        {stepStatus}
      </span>
    </div>
  )

  const testExecutionContent = (
    <section className="test-execution-content">
      <div className="test-execution-hero">
        <span className="small-label">Guided Workflow</span>
        <h2>QualityOps Test Execution Workflow</h2>
        <p>
          Execute the generated QA scenarios through Azure DevOps, UiPath Test Manager, automated
          triage, defect creation, and final QA reporting.
        </p>
      </div>

      <div className="execution-stepper-flow">
        <section className="dashboard-card execution-step-card ado-sync-section" data-section="azureDevOpsSync">
          {renderExecutionStepHeader(
            1,
            'Azure DevOps Test Case Creation',
            'Create Azure DevOps Test Case work items from generated scenarios.',
            adoTestCaseStepStatus
          )}

      <div className="memory-feedback-summary-grid">
        <div className="summary-item">
          <span>Total Generated</span>
          <strong>{testCaseReviewCounts.total}</strong>
        </div>
        <div className="summary-item">
          <span>Approved</span>
          <strong>{testCaseReviewCounts.approved}</strong>
        </div>
        <div className="summary-item">
          <span>Rejected</span>
          <strong>{testCaseReviewCounts.rejected}</strong>
        </div>
        <div className="summary-item">
          <span>Pending</span>
          <strong>{testCaseReviewCounts.pending}</strong>
        </div>
      </div>

      <div className="test-case-writeback-actions">
        <button
          className="create-test-cases-button"
          onClick={handleCreateTestCases}
          disabled={isCreatingTestCases || testCaseReviewCounts.approved === 0}
        >
          {isCreatingTestCases
            ? 'Creating approved test cases...'
            : 'Create Approved Test Cases in Azure DevOps'}
        </button>
      </div>

      {testCaseWriteBackOutput ? (
        <div className="test-case-summary">
          <div className="test-case-summary-header">
            <div>
              <span className="small-label">Azure DevOps WriteBack Result</span>
              <h4>Created Test Cases</h4>
            </div>

            <span className="created-count-badge">
              {testCaseWriteBackOutput.createdTestCases?.length ?? 0} created
            </span>
          </div>

          {testCaseWriteBackOutput.createdTestCases?.length ? (
            <div className="created-test-case-list">
              {testCaseWriteBackOutput.createdTestCases.map((testCase, index) => (
                <article
                  className="created-test-case-item"
                  key={`${testCase.scenarioId || 'scenario'}-${testCase.testCaseId || index}`}
                >
                  <span className="created-test-case-id">
                    {testCase.testCaseId ? `Azure DevOps Test Case ${testCase.testCaseId}` : 'Azure DevOps Test Case'}
                  </span>
                  <strong>{testCase.title || 'Untitled test case'}</strong>
                  {testCase.url && (
                    <a href={testCase.url} target="_blank" rel="noreferrer">
                      Open in Azure DevOps
                    </a>
                  )}
                </article>
              ))}
            </div>
          ) : (
            <p className="empty-scenarios">No test cases were created.</p>
          )}

          {testCaseWriteBackOutput.failedScenarios?.length ? (
            <div className="failed-scenario-summary">
              <span className="scenario-section-label">Failed Scenarios</span>
              <div className="failed-scenario-grid">
                {testCaseWriteBackOutput.failedScenarios.map((scenario, index) => (
                  <article className="failed-scenario-card" key={`${scenario.scenarioId || 'failed'}-${index}`}>
                    <strong>{scenario.scenarioId || `Scenario ${index + 1}`}</strong>
                    <p>{scenario.title || scenario.errorMessage || 'Creation failed'}</p>
                  </article>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : (
        <p className="empty-scenarios">Create test cases after generated scenarios are available.</p>
      )}
      </section>

      <section
        className="dashboard-card execution-step-card test-manager-sync-section"
        data-section="testManagerSync"
      >
        {renderExecutionStepHeader(
          2,
            'UiPath Test Manager Sync',
          'Sync generated test cases to UiPath Test Manager and create/reuse the Test Set.',
          testManagerSyncStepStatus
        )}

        <div className="test-manager-sync-controls">
          <button
            className="test-manager-sync-button"
            onClick={handleSyncTestManager}
            disabled={isSyncingTestManager}
          >
            {isSyncingTestManager
              ? 'Syncing to UiPath Test Manager...'
              : 'Sync to UiPath Test Manager'}
          </button>
        </div>

        <p className="sync-mode-helper">
          Creates requirement, test cases, links, and test set in UiPath Test Manager using secure API configuration.
        </p>

        {!canSyncTestManager && (
          <p className="readiness-helper">
            Generate test scenarios and risk-based execution plan before preparing Test Manager
            sync.
          </p>
        )}

        {status === 'Error' && statusMessage.toLowerCase().includes('test manager') && (
          <div className="result-box error">
            <strong>Test Manager Sync Error</strong>
            <p>{statusMessage}</p>
          </div>
        )}

        {isSyncingTestManager && (
          <div className="result-box running">
            <strong>Preparing Test Manager sync</strong>
            <p>{displayStatusMessage}</p>
          </div>
        )}

        {testManagerWriteBackOutput && (
          <div className="test-manager-sync-output">
            {testManagerWriteBackOutput.syncStatus === 'ConfigurationRequired' ? (
              <div className="test-manager-warning-panel">
                <strong>Configuration Required</strong>
                <p>{renderTechnicalText(testManagerWriteBackOutput.nextAction)}</p>
              </div>
            ) : null}

            {testManagerWriteBackOutput.syncStatus === 'ReadyToSync' ? (
              <div className="test-manager-warning-panel">
                <strong>Unexpected sync preparation response received.</strong>
                <p>Please verify the Test Manager sync configuration.</p>
              </div>
            ) : null}

            <div className="readiness-grid test-manager-sync-grid">
              <div className="summary-item">
                <span>Sync Status</span>
                <strong>{testManagerSyncStatusLabel}</strong>
              </div>
              <div className="summary-item">
                <span>Sync Mode</span>
                <strong>{testManagerWriteBackOutput.syncMode || '-'}</strong>
              </div>
              <div className="summary-item">
                <span>Project Key</span>
                <strong>{testManagerWriteBackOutput.testManagerProjectKey || '-'}</strong>
              </div>
              <div className="summary-item">
                <span>Requirements Prepared</span>
                <strong>{testManagerWriteBackOutput.summary?.requirementsPrepared ?? 0}</strong>
              </div>
              <div className="summary-item">
                <span>Created Test Cases</span>
                <strong>{latestCreatedTestCaseIds.length}</strong>
              </div>
              <div className="summary-item">
                <span>Reused Test Cases</span>
                <strong>{latestReusedTestCaseIds.length}</strong>
              </div>
              <div className="summary-item">
                <span>Total Test Cases</span>
                <strong>
                  {latestAllTestCaseIds.length || latestAutomationLinkTestCaseIds.length}
                </strong>
              </div>
              <div className="summary-item">
                <span>Test Case Reuse Enabled</span>
                <strong>
                  {testManagerWriteBackOutput.testCaseReuseEnabled === undefined
                    ? '-'
                    : testManagerWriteBackOutput.testCaseReuseEnabled
                      ? 'Yes'
                      : 'No'}
                </strong>
              </div>
              <div className="summary-item">
                <span>Created Test Set ID</span>
                <strong>{testManagerWriteBackOutput.createdTestSetId ?? '-'}</strong>
              </div>
              <div className="summary-item">
                <span>Links Prepared</span>
                <strong>{testManagerWriteBackOutput.summary?.linksPrepared ?? 0}</strong>
              </div>
              <div className="summary-item">
                <span>Test Sets Prepared</span>
                <strong>{testManagerWriteBackOutput.summary?.testSetsPrepared ?? 0}</strong>
              </div>
              <div className="summary-item">
                <span>Test Set Name</span>
                <strong>{testManagerWriteBackOutput.testSetPayload?.name || '-'}</strong>
              </div>
              <div className="summary-item">
                <span>Next Action</span>
                <strong>{renderTechnicalText(testManagerWriteBackOutput.nextAction)}</strong>
              </div>
            </div>

            {testManagerWriteBackOutput.blockedReasons?.length ? (
              <div className="blocked-reasons-panel">
                <span className="scenario-section-label">Blocked Reasons</span>
                <ul className="compact-list">
                  {testManagerWriteBackOutput.blockedReasons.map((reason, index) => (
                    <li key={`${reason}-${index}`}>{renderTechnicalText(reason)}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {testManagerWriteBackOutput.testCasePayloads?.length ? (
              <div className="prepared-test-case-list">
                {testManagerWriteBackOutput.testCasePayloads.map((testCase, index) => (
                  <article
                    className="prepared-test-case-card"
                    key={`${testCase.scenarioId || 'tm-test-case'}-${index}`}
                  >
                    <span className="scenario-id">
                      {getTestManagerCaseResultStatus(index)}
                    </span>
                    <strong>
                      {testCase.scenarioTitle || testCase.name || 'Untitled test case'}
                    </strong>
                    <div className="prepared-test-case-meta">
                      <span>Scenario: {testCase.scenarioId || `scenario-${index + 1}`}</span>
                      <span>{testCase.priority || 'Priority N/A'}</span>
                      <span>{testCase.testType || 'Type N/A'}</span>
                      <span>{testCase.steps?.length ?? 0} steps</span>
                      <span>Test Case ID: {getTestManagerCaseResultId(index) || '-'}</span>
                      <span>
                        Link: {testCase.linkStatus || (testManagerWriteBackOutput.summary?.linksPrepared ? 'Prepared' : '-')}
                      </span>
                      <span>
                        Test Set: {testCase.membershipStatus || (testManagerWriteBackOutput.summary?.testSetsPrepared ? 'Prepared' : '-')}
                      </span>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <p className="empty-scenarios">No prepared Test Manager test cases were returned.</p>
            )}
          </div>
        )}
      </section>

      <section
        className="dashboard-card execution-step-card automation-link-section"
        data-section="automationMapping"
      >
        {renderExecutionStepHeader(
          3,
          'Automation Mapping',
          'Map Test Manager test cases to UiPath automated test package entry points.',
          automationMappingStepStatus
        )}

        <div className="section-action-row">
          <button
            className="automation-link-button"
            onClick={handleMapAutomatedTestCases}
            disabled={automationLinkLoading || !canMapAutomatedTestCases}
          >
            {automationLinkLoading ? 'Mapping Automated Test Cases...' : 'Map Automated Test Cases'}
          </button>
        </div>

        {!canMapAutomatedTestCases && (
          <p className="readiness-helper">
            Run UiPath Test Manager Sync first to create UiPath Test Manager test cases.
          </p>
        )}

        {automationLinkLoading && (
          <div className="result-box running">
            <strong>Mapping automated test cases</strong>
            <p>{displayStatusMessage}</p>
          </div>
        )}

        {automationLinkError && (
          <div className="result-box error">
            <strong>Mapping failed</strong>
            <p>{automationLinkError}</p>
          </div>
        )}

        {automationLinkResult && (
          <div className="automation-link-output">
            <div className="test-manager-success-panel">
              <strong>Automation Mapping Completed</strong>
              <p>
                The automated test cases are mapped successfully. Open UiPath Test Manager,
                select the generated Test Set, and click Execute - Automated. After execution
                completes, return here and click Analyze Test Results.
              </p>
              {latestTestSetId && (
                <div className="test-manager-handoff">
                  <span>Test Set ID: {renderTechnicalText(latestTestSetId)}</span>
                  <button
                    type="button"
                    className="test-manager-open-link"
                    onClick={handleOpenTestSet}
                    disabled={!canOpenTestManagerTestSet}
                  >
                    Open Test Set in UiPath Test Manager
                  </button>
                </div>
              )}
            </div>

            <details className="details-section automation-diagnostics">
              <summary>Diagnostics</summary>
              <div className="readiness-grid automation-link-grid">
                <div className="summary-item">
                  <span>automationLinkStatus</span>
                  <strong>
                    {sanitizeUserFacingText(automationLinkResult.automationLinkStatus || '-')}
                  </strong>
                </div>
                <div className="summary-item">
                  <span>linkedCount</span>
                  <strong>{automationLinkResult.linkedCount ?? 0}</strong>
                </div>
                <div className="summary-item">
                  <span>failedCount</span>
                  <strong>{automationLinkResult.failedCount ?? 0}</strong>
                </div>
                <div className="summary-item">
                  <span>packageIdentifier</span>
                  <strong>
                    {renderTechnicalText(
                      automationLinkResult.packageIdentifier ||
                        AUTOMATION_LINK_PACKAGE_DISPLAY_NAME
                    )}
                  </strong>
                </div>
                <div className="summary-item">
                  <span>responseStatusCode</span>
                  <strong>{automationLinkResult.responseStatusCode ?? '-'}</strong>
                </div>
              </div>
            </details>

            {automationLinkResult.linkedMappings?.length ? (
              <div className="readiness-table-wrap">
                <table className="risk-plan-table automation-link-table">
                  <thead>
                    <tr>
                      <th>Test Case ID</th>
                      <th>Automated Test Case</th>
                      <th>Entry Point</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {automationLinkResult.linkedMappings.map((mapping, index) => (
                      <tr key={`${getMappingTestCaseId(mapping, index)}-${index}`}>
                        <td data-label="Test Case ID">
                          {renderTechnicalText(getMappingTestCaseId(mapping, index))}
                        </td>
                        <td data-label="Automated Test Case">
                          <strong>{getMappingAutomatedTestCase(mapping)}</strong>
                        </td>
                        <td data-label="Entry Point">
                          {renderTechnicalText(mapping.entryPoint || mapping.simulatorProfile || '-')}
                        </td>
                        <td data-label="Status">
                          {sanitizeUserFacingText(mapping.status || '-')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="empty-scenarios">No mapped test cases were returned.</p>
            )}

            {automationLinkResult.blockedReasons?.length ? (
              <div className="blocked-reasons-panel">
                <span className="scenario-section-label">Mapping Blockers</span>
                <div className="readiness-grid automation-link-grid">
                  <div className="summary-item">
                    <span>Package Identifier</span>
                    <strong>
                      {renderTechnicalText(
                        automationLinkResult.packageIdentifier ||
                          AUTOMATION_LINK_PACKAGE_IDENTIFIER
                      )}
                    </strong>
                  </div>
                  <div className="summary-item">
                    <span>Requested Entry Point</span>
                    <strong>{renderTechnicalText(AUTOMATION_DEFAULT_ENTRY_POINT)}</strong>
                  </div>
                </div>
                <ul className="compact-list">
                  {automationLinkResult.blockedReasons.map((reason, index) => (
                    <li key={`${reason}-${index}`}>{renderTechnicalText(reason)}</li>
                  ))}
                </ul>
                {automationLinkResult.linkedMappings?.length ? (
                  <ul className="compact-list">
                    {automationLinkResult.linkedMappings.map((mapping, index) => (
                      <li key={`mapping-blocker-${getMappingTestCaseId(mapping, index)}-${index}`}>
                        {renderTechnicalText(getMappingTestCaseId(mapping, index))} -{' '}
                        {renderTechnicalText(mapping.entryPoint || mapping.simulatorProfile || AUTOMATION_DEFAULT_ENTRY_POINT)}:{' '}
                        {renderTechnicalText(mapping.blockedReason || mapping.status || 'Mapping blocked')}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : null}
          </div>
        )}
      </section>

      <section className="dashboard-card execution-step-card test-manager-manual-execution-section">
        {renderExecutionStepHeader(
          4,
          'Execute in UiPath Test Manager',
          'Open the mapped Test Set in UiPath Test Manager and run Execute -> Automated.',
          manualExecutionStepStatus
        )}
        <div className="manual-instruction-card">
          <strong>Manual execution required</strong>
          <p>
            Open the mapped Test Set in UiPath Test Manager, choose Execute, then select Automated.
            After the run completes, return here and load the latest execution for triage.
          </p>
          {latestTestSetId || testManagerProjectUrl ? (
            <button
              type="button"
              className="test-manager-open-link"
              onClick={handleOpenTestSet}
              disabled={!canOpenTestManagerTestSet}
            >
              Open Test Set in UiPath Test Manager
            </button>
          ) : (
            <p className="readiness-helper">Complete automation mapping to get the Test Set link.</p>
          )}
        </div>
      </section>

      <section
        className="dashboard-card execution-step-card analyze-test-results-section"
        data-section="testResultTriage"
      >
        {renderExecutionStepHeader(
          5,
          'Test Result Triage',
          'Load Test Manager executions, analyze failed test results, classify failures, and prepare defect recommendations.',
          triageStepStatus
        )}

        <div className="test-result-triage-controls">
          <button
            className="test-result-triage-button"
            onClick={handleLoadTestExecutions}
            disabled={triageLoadingExecutions || !automationMappingCompleted}
          >
            {triageLoadingExecutions ? 'Loading Test Executions...' : 'Load Test Executions'}
          </button>

          <label className="triage-execution-field">
            Select Test Execution
            <select
              value={selectedExecution?.testExecutionId || ''}
              onChange={(event) => {
                const execution =
                  triageExecutions.find(
                    (item) => String(item.testExecutionId || '') === event.target.value
                  ) || null

                setSelectedExecution(execution)
                setTriageAnalysisResult(null)
                setSelectedTriageResultKeys([])
                setExpandedTriageResultKeys([])
                setTriageClassificationOverrides({})
                setDefectCreationResults([])
                setFinalReportGeneratedAt('')
              }}
              disabled={
                !automationMappingCompleted || !triageExecutions.length || triageLoadingExecutions
              }
            >
              <option value="">Select an execution</option>
              {triageExecutions.map((execution, index) => (
                <option
                  key={`${execution.testExecutionId || 'execution'}-${index}`}
                  value={execution.testExecutionId || ''}
                >
                  {sanitizeUserFacingText(execution.executionName || `Execution ${index + 1}`)} -
                  Run {execution.runId ?? '-'} - {sanitizeUserFacingText(execution.status || '-')}
                </option>
              ))}
            </select>
          </label>

          <label className="triage-parent-field">
            Parent PBI / Story ID
            <input
              type="text"
              value={adoParentStoryId}
              onChange={(event) => setAdoParentStoryId(event.target.value)}
              placeholder="Enter Azure DevOps PBI/User Story ID"
            />
          </label>

          <button
            className="test-result-triage-button secondary-triage-button"
            onClick={handleAnalyzeTestResults}
            disabled={triageAnalyzing || !automationMappingCompleted || !selectedExecution}
          >
            {triageAnalyzing ? 'Analyzing Test Results...' : 'Analyze Test Results'}
          </button>
        </div>

        {!automationMappingCompleted && (
          <p className="readiness-helper">
            Complete automation mapping before analyzing test results.
          </p>
        )}

        {triageLoadingExecutions || triageAnalyzing || triageCreatingDefects ? (
          <div className="result-box running">
            <strong>
              {triageCreatingDefects
                ? 'Creating defects'
                : triageAnalyzing
                  ? 'Analyzing failed test results'
                  : 'Loading Test Manager executions'}
            </strong>
            <p>{displayStatusMessage}</p>
          </div>
        ) : null}

        {triageError && (
          <div className="result-box error">
            <strong>Test result triage failed</strong>
            <p>{triageError}</p>
          </div>
        )}

        {triageMessage && !triageError && (
          <div className={`result-box ${triageMessage.includes('No ') ? 'ready' : 'completed'}`}>
            <strong>Test result triage status</strong>
            <p>{triageMessage}</p>
          </div>
        )}

        {triageExecutionSummary && (
          <div className="test-result-triage-output">
            <div className="triage-metric-grid">
              <div className="triage-metric-card">
                <span>Total Tests</span>
                <strong>{triageExecutionSummary.totalTests ?? 0}</strong>
              </div>
              <div className="triage-metric-card passed">
                <span>Passed</span>
                <strong>{triageExecutionSummary.passed ?? 0}</strong>
              </div>
              <div className="triage-metric-card failed">
                <span>Failed</span>
                <strong>{triageExecutionSummary.failed ?? 0}</strong>
              </div>
              <div className="triage-metric-card skipped">
                <span>Skipped</span>
                <strong>{triageExecutionSummary.skipped ?? 0}</strong>
              </div>
              <div className="triage-metric-card">
                <span>Execution Status</span>
                <strong>
                  {renderTechnicalText(
                    triageExecutionSummary.status || triageExecutionSummary.testManagerStatus
                  )}
                </strong>
              </div>
              <div className="triage-metric-card">
                <span>Execution Type</span>
                <strong>{renderTechnicalText(triageExecutionSummary.executionType)}</strong>
              </div>
              <div className="triage-metric-card">
                <span>Runtime Type</span>
                <strong>{renderTechnicalText(triageExecutionSummary.runtimeType)}</strong>
              </div>
            </div>

            <section className="classification-summary-section">
              <span className="scenario-section-label">Classification Summary</span>
              <div className="classification-pill-row">
                {TRIAGE_CLASSIFICATIONS.map((classification) => (
                  <span
                    className={`classification-badge ${getClassificationClass(classification)}`}
                    key={classification}
                  >
                    {classification}: {classificationCounts[classification] ?? 0}
                  </span>
                ))}
              </div>
            </section>
          </div>
        )}

        {triageAnalysisResult && !triageError && failedTriageResults.length === 0 && (
          <p className="empty-scenarios">No failed test results found for this execution.</p>
        )}

        {failedTriageResults.length > 0 && (
          <div className="triage-card-list">
            {failedTriageResults.map((triageResult, index) => {
              const resultKey = getTriageResultKey(triageResult, index)
              const isSelected = selectedTriageResultKeys.includes(resultKey)
              const isExpanded = expandedTriageResultKeys.includes(resultKey)
              const selectedClassification =
                triageClassificationOverrides[resultKey] || getDisplayClassification(triageResult)
              const recommendedAction = getClassificationRecommendation(
                selectedClassification,
                triageResult.recommendedAction
              )
              const structuredEvidenceSections = getStructuredEvidenceSections(triageResult)
              const copyEvidenceText = structuredEvidenceSections
                .map(([label, content]) => `${label}\n${content}`)
                .join('\n\n')

              return (
                <article className="triage-result-card" key={resultKey}>
                  <div className="triage-result-card-main">
                    <div className="triage-card-compact-row">
                      <div className="triage-card-left">
                        <label className="triage-select-control">
                          <input
                            className="triage-result-checkbox"
                            type="checkbox"
                            checked={isSelected}
                            onChange={(event) => {
                              setSelectedTriageResultKeys((previous) =>
                                event.target.checked
                                  ? [...previous, resultKey]
                                  : previous.filter((key) => key !== resultKey)
                              )
                            }}
                          />
                          <span className="triage-result-name">
                            {renderTechnicalText(
                              triageResult.testCaseName || triageResult.testCaseId
                            )}
                          </span>
                        </label>
                        <div className="triage-result-meta-line">
                          Result: {sanitizeUserFacingText(triageResult.resultStatus || '-')} | Robot:{' '}
                          {sanitizeUserFacingText(triageResult.robotName || '-')} | Host:{' '}
                          {sanitizeUserFacingText(triageResult.hostMachine || '-')}
                        </div>
                        <p className="triage-result-recommendation-line">
                          <strong>Recommended:</strong> {recommendedAction}
                        </p>
                        <label className="triage-override-field">
                          <span>Classification:</span>
                          <select
                            className="triage-classification-select"
                            value={selectedClassification}
                            onChange={(event) => {
                              setTriageClassificationOverrides((previous) => ({
                                ...previous,
                                [resultKey]: event.target.value,
                              }))
                            }}
                          >
                            {TRIAGE_CLASSIFICATIONS.map((classification) => (
                              <option key={classification} value={classification}>
                                {classification}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>

                      <div className="triage-card-actions">
                        <span
                          className={`classification-badge ${getClassificationClass(
                            selectedClassification
                          )}`}
                        >
                          {selectedClassification}
                        </span>
                        <button
                          className="view-evidence-button"
                          type="button"
                          onClick={() => {
                            setExpandedTriageResultKeys((previous) =>
                              previous.includes(resultKey)
                                ? previous.filter((key) => key !== resultKey)
                                : [...previous, resultKey]
                            )
                          }}
                        >
                          {isExpanded ? 'Hide Evidence' : 'View Evidence'}
                        </button>
                        {triageResult.linkToTestCaseLog ? (
                          <a
                            className="test-manager-open-link compact"
                            href={triageResult.linkToTestCaseLog}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Open in Test Manager
                          </a>
                        ) : (
                          <span className="triage-muted-action">No Test Manager log</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="triage-evidence-panel">
                      <div className="triage-evidence-toolbar">
                        <span>Evidence</span>
                        <button
                          className="copy-evidence-button"
                          type="button"
                          onClick={() => {
                            void navigator.clipboard?.writeText(copyEvidenceText)
                          }}
                        >
                          Copy Evidence
                        </button>
                      </div>
                      {structuredEvidenceSections.map(([label, content, isLogSection]) => (
                        <div className="triage-evidence-section" key={label}>
                          <span>{label}</span>
                          <p className={isLogSection ? 'triage-log-text' : undefined}>{content}</p>
                        </div>
                      ))}
                      <details className="triage-technical-details">
                        <summary>Technical Details</summary>
                        <div className="technical-details-grid compact">
                          {[
                            ['testCaseId', triageResult.testCaseId],
                            ['testCaseLogId', triageResult.variationId],
                            ['linkToTestCaseLog', triageResult.linkToTestCaseLog],
                            ['rawEvidence', triageResult.evidence],
                          ].map(([label, value]) => (
                            <div key={label}>
                              <span>{label}</span>
                              <strong>
                                {renderTechnicalText(
                                  value === undefined || value === null ? '-' : String(value)
                                )}
                              </strong>
                            </div>
                          ))}
                        </div>
                      </details>
                    </div>
                  )}
                </article>
              )
            })}
          </div>
        )}

        {triageAnalysisResult && (
          <details className="technical-details-accordion">
            <summary>Technical Details</summary>
            <div className="technical-details-grid">
              {[
                ['executionSummaryUrlUsed', triageAnalysisResult.result?.executionSummaryUrlUsed ?? triageAnalysisResult.executionSummaryUrlUsed],
                ['testCaseLogsUrlUsed', triageAnalysisResult.result?.testCaseLogsUrlUsed ?? triageAnalysisResult.testCaseLogsUrlUsed],
                ['totalResultRows', triageAnalysisResult.result?.totalResultRows ?? triageAnalysisResult.totalResultRows],
                ['failedResultRows', triageAnalysisResult.result?.failedResultRows ?? triageAnalysisResult.failedResultRows],
                ['robotLogsFetchedCount', triageAnalysisResult.result?.robotLogsFetchedCount ?? triageAnalysisResult.robotLogsFetchedCount],
                ['assertionsFetchedCount', triageAnalysisResult.result?.assertionsFetchedCount ?? triageAnalysisResult.assertionsFetchedCount],
                ['responseStatusCode', triageAnalysisResult.result?.responseStatusCode ?? triageAnalysisResult.responseStatusCode],
              ].map(([label, value]) => (
                <div key={label}>
                  <span>{label}</span>
                  <strong>{renderTechnicalText(value === undefined || value === null ? '-' : String(value))}</strong>
                </div>
              ))}
            </div>
          </details>
        )}
      </section>

        <section
          className="dashboard-card execution-step-card ado-defect-creation-section"
          data-section="bugCreation"
        >
          {renderExecutionStepHeader(
            6,
            'Azure DevOps Bug Creation',
            'Create Azure DevOps Bugs from selected failed tests and link them to the parent PBI.',
            defectCreationStepStatus
          )}

        <div className="triage-sticky-footer">
          <span>Create Azure DevOps Bugs</span>
          <span>Selected failures: {selectedTriageResultKeys.length}</span>
          <button
            className="create-defect-button"
            onClick={handleCreateDefects}
            disabled={triageCreatingDefects || !canCreateAdoBug}
          >
            {triageCreatingDefects ? 'Creating Azure DevOps Bug...' : 'Create Azure DevOps Bug'}
          </button>
        </div>

        {defectCreationResults.length > 0 && (
          <div className="defect-status-list">
            {defectCreationResults.map((defectResult, index) => {
              const syncStatus =
                defectResult.output?.defectSyncStatus ||
                defectResult.output?.defectCreationStatus ||
                defectResult.status
              const statusClass = getDefectStatusClass(syncStatus)

              return (
                <article
                  className={`defect-status-card ${statusClass}`}
                  key={`${defectResult.testCaseId}-${index}`}
                >
                  <div className="defect-status-header">
                    <div>
                      <span className="small-label">Azure DevOps Defect</span>
                      <strong>
                        {statusClass === 'not-ready'
                          ? 'Azure DevOps Bug creation failed'
                          : 'Azure DevOps Bug created successfully'}
                      </strong>
                    </div>
                    <span className={`readiness-status-badge ${statusClass}`}>
                      {sanitizeUserFacingText(syncStatus)}
                    </span>
                  </div>
                  <div className="defect-status-grid">
                    <div>
                      <span>Bug ID</span>
                      <strong>
                        {renderTechnicalText(
                          defectResult.output?.adoBugId || defectResult.output?.defectId
                        )}
                      </strong>
                    </div>
                    <div>
                      <span>Parent PBI / Story ID</span>
                      <strong>{renderTechnicalText(defectResult.output?.adoParentId || adoParentStoryId)}</strong>
                    </div>
                    <div>
                      <span>Classification</span>
                      <strong>
                        {renderTechnicalText(
                          defectResult.output?.classification || defectResult.classification
                        )}
                      </strong>
                    </div>
                    <div>
                      <span>Defect System</span>
                      <strong>{renderTechnicalText(defectResult.output?.defectSystem || 'Azure DevOps')}</strong>
                    </div>
                    <div>
                      <span>Test Case ID</span>
                      <strong>{renderTechnicalText(defectResult.testCaseId)}</strong>
                    </div>
                    <div>
                      <span>Test Manager Evidence Link</span>
                      {defectResult.testManagerEvidenceLink ? (
                        <a
                          href={defectResult.testManagerEvidenceLink}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Open Test Manager Evidence
                        </a>
                      ) : (
                        <strong>-</strong>
                      )}
                    </div>
                  </div>
                  {defectResult.output?.adoBugUrl ? (
                    <a
                      className="test-manager-open-link compact"
                      href={defectResult.output.adoBugUrl}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open Azure DevOps Bug
                    </a>
                  ) : null}
                  {(defectResult.output?.blockedReasons?.length ||
                    defectResult.output?.result?.blockedReasons?.length) ? (
                    <ul className="compact-list">
                      {[
                        ...(defectResult.output?.blockedReasons ?? []),
                        ...(defectResult.output?.result?.blockedReasons ?? []),
                      ].map((reason, reasonIndex) => (
                        <li key={`${reason}-${reasonIndex}`}>{renderTechnicalText(reason)}</li>
                      ))}
                    </ul>
                  ) : null}
                  <p>{defectResult.message}</p>
                </article>
              )
            })}
          </div>
        )}
        </section>

        <section
          className="dashboard-card execution-step-card final-report-section"
          data-section="finalQaReport"
        >
          {renderExecutionStepHeader(
            7,
            'Final QA Report',
            'Generate a stylish QA sign-off report with summary cards, charts, defect links, risk observations, and recommendation.',
            finalReportStepStatus
          )}

          <div className="section-action-row">
            <button
              className="final-report-button"
              type="button"
              onClick={handleGenerateFinalReport}
              disabled={!triageAnalysisResult}
            >
              Generate Final QA Report
            </button>
          </div>

          {!triageAnalysisResult && (
            <p className="readiness-helper">
              Analyze Test Results before generating the final QA report.
            </p>
          )}

          {finalReportGeneratedAt && (
            <div className="final-report-preview" id="final-qa-report-preview">
              <div className="report-hero">
                <div>
                  <span className="small-label">QualityOps QA Sign-off Report</span>
                  <h4>QualityOps QA Sign-off Report</h4>
                  <div className="report-meta-grid">
                    <div>
                      <span>Parent PBI / Story ID</span>
                      <strong>{renderTechnicalText(adoParentStoryId || '-')}</strong>
                    </div>
                    <div>
                      <span>Execution Name</span>
                      <strong>{renderTechnicalText(selectedExecutionName)}</strong>
                    </div>
                    <div>
                      <span>Generated Date / Time</span>
                      <strong>{reportGeneratedDisplay}</strong>
                    </div>
                  </div>
                </div>
                <span className={`report-status-badge ${finalQaStatus.toLowerCase().replace(/\s+/g, '-')}`}>
                  {finalQaStatus}
                </span>
              </div>

              <div className="report-summary-card-grid">
                {[
                  ['Total Tests', totalTests, 'neutral'],
                  ['Passed', passedTests, 'passed'],
                  ['Failed', failedTests, 'failed'],
                  ['Skipped', skippedTests, 'skipped'],
                  ['Product Defects', productDefectCount, 'failed'],
                  ['Automation Issues', automationIssueCount, 'warning'],
                  ['Environment Issues', environmentIssueCount, 'info'],
                  ['Azure DevOps Bugs Created', createdAdoBugs.length, 'ado'],
                ].map(([label, value, tone]) => (
                  <div className={`report-summary-card ${tone}`} key={label}>
                    <span>{label}</span>
                    <strong>{value}</strong>
                  </div>
                ))}
              </div>

              <div className="report-chart-grid">
                <div className="report-chart-card">
                  <div className="report-card-header">
                    <span className="scenario-section-label">Pass / Fail / Skipped</span>
                    <strong>{totalTests} tests</strong>
                  </div>
                  {[
                    ['Passed', passedTests, '#16a34a'],
                    ['Failed', failedTests, '#dc2626'],
                    ['Skipped', skippedTests, '#64748b'],
                  ].map(([label, value, color]) => {
                    const width = totalTests ? Math.max((Number(value) / totalTests) * 100, 3) : 0

                    return (
                      <div className="report-bar-row" key={label}>
                        <span>{label}</span>
                        <div className="report-bar-track">
                          <div
                            className="report-bar-fill"
                            style={{ width: `${width}%`, background: String(color) }}
                          />
                        </div>
                        <strong>{value}</strong>
                      </div>
                    )
                  })}
                </div>

                <div className="report-chart-card">
                  <div className="report-card-header">
                    <span className="scenario-section-label">Failure Classification</span>
                    <strong>{failedTriageResults.length} failures</strong>
                  </div>
                  {TRIAGE_CLASSIFICATIONS.map((classification) => {
                    const value = classificationCounts[classification] ?? 0
                    const width = failedTriageResults.length
                      ? Math.max((value / failedTriageResults.length) * 100, value ? 3 : 0)
                      : 0

                    return (
                      <div className="report-bar-row" key={classification}>
                        <span>{classification}</span>
                        <div className="report-bar-track">
                          <div
                            className={`report-bar-fill ${getClassificationClass(classification)}`}
                            style={{ width: `${width}%` }}
                          />
                        </div>
                        <strong>{value}</strong>
                      </div>
                    )
                  })}
                </div>

                <div className="report-chart-card">
                  <div className="report-card-header">
                    <span className="scenario-section-label">Azure DevOps Bugs by Classification</span>
                    <strong>{defectCreationResults.length} requests</strong>
                  </div>
                  {TRIAGE_CLASSIFICATIONS.map((classification) => {
                    const value = adoBugCountsByClassification[classification] ?? 0
                    const width = defectCreationResults.length
                      ? Math.max((value / defectCreationResults.length) * 100, value ? 3 : 0)
                      : 0

                    return (
                      <div className="report-bar-row" key={classification}>
                        <span>{classification}</span>
                        <div className="report-bar-track">
                          <div
                            className={`report-bar-fill ${getClassificationClass(classification)}`}
                            style={{ width: `${width}%` }}
                          />
                        </div>
                        <strong>{value}</strong>
                      </div>
                    )
                  })}
                </div>
              </div>

              <div className="report-table-wrap">
                <div className="report-card-header">
                  <span className="scenario-section-label">Triage Summary</span>
                  <strong>{failedTriageResults.length} failed / reviewed tests</strong>
                </div>
                <table className="risk-plan-table report-table">
                  <thead>
                    <tr>
                      <th>Test Case</th>
                      <th>Result</th>
                      <th>Classification</th>
                      <th>Recommended Action</th>
                      <th>Azure DevOps Bug</th>
                      <th>Test Manager Evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {failedTriageResults.length ? (
                      failedTriageResults.map((triageResult, index) => {
                        const resultKey = getTriageResultKey(triageResult, index)
                        const classification =
                          triageClassificationOverrides[resultKey] ||
                          getDisplayClassification(triageResult)
                        const defect = defectCreationResults.find(
                          (defectResult) =>
                            defectResult.testCaseId === triageResult.testCaseId ||
                            defectResult.testCaseId === resultKey
                        )
                        const bugId = defect?.output?.adoBugId || defect?.output?.defectId

                        return (
                          <tr key={`${resultKey}-report`}>
                            <td data-label="Test Case">
                              {renderTechnicalText(
                                triageResult.testCaseName || triageResult.testCaseId
                              )}
                            </td>
                            <td data-label="Result">
                              {renderTechnicalText(triageResult.resultStatus || 'Failed')}
                            </td>
                            <td data-label="Classification">
                              <span
                                className={`classification-badge ${getClassificationClass(
                                  classification
                                )}`}
                              >
                                {classification}
                              </span>
                            </td>
                            <td data-label="Recommended Action">
                              {getClassificationRecommendation(
                                classification,
                                triageResult.recommendedAction
                              )}
                            </td>
                            <td data-label="Azure DevOps Bug">
                              {defect?.output?.adoBugUrl ? (
                                <a href={defect.output.adoBugUrl} target="_blank" rel="noreferrer">
                                  {bugId ? `Bug ${bugId}` : 'Open Azure DevOps Bug'}
                                </a>
                              ) : (
                                renderTechnicalText(bugId || '-')
                              )}
                            </td>
                            <td data-label="Test Manager Evidence">
                              {triageResult.linkToTestCaseLog ? (
                                <a
                                  href={triageResult.linkToTestCaseLog}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  Open Evidence
                                </a>
                              ) : (
                                '-'
                              )}
                              <details className="report-evidence-details">
                                <summary>Evidence Details</summary>
                                {getStructuredEvidenceSections(triageResult)
                                  .slice(0, 2)
                                  .map(([label, content]) => (
                                    <div key={label}>
                                      <span>{label}</span>
                                      <p>{content}</p>
                                    </div>
                                  ))}
                              </details>
                            </td>
                          </tr>
                        )
                      })
                    ) : (
                      <tr>
                        <td colSpan={6}>No failed test results were found for this execution.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              <div className="report-table-wrap">
                <div className="report-card-header">
                  <span className="scenario-section-label">Defect Summary</span>
                  <strong>{defectCreationResults.length} Azure DevOps defect records</strong>
                </div>
                <table className="risk-plan-table report-table">
                  <thead>
                    <tr>
                      <th>Bug ID</th>
                      <th>Bug Title</th>
                      <th>Classification</th>
                      <th>Parent PBI</th>
                      <th>Open Azure DevOps Bug Link</th>
                    </tr>
                  </thead>
                  <tbody>
                    {defectCreationResults.length ? (
                      defectCreationResults.map((defectResult, index) => {
                        const bugId = defectResult.output?.adoBugId || defectResult.output?.defectId
                        const title =
                          defectResult.output?.defectName ||
                          defectResult.message ||
                          'Azure DevOps Bug'

                        return (
                          <tr key={`${defectResult.testCaseId}-defect-report-${index}`}>
                            <td data-label="Bug ID">{renderTechnicalText(bugId || '-')}</td>
                            <td data-label="Bug Title">{renderTechnicalText(title)}</td>
                            <td data-label="Classification">
                              {renderTechnicalText(
                                defectResult.output?.classification ||
                                  defectResult.classification ||
                                  '-'
                              )}
                            </td>
                            <td data-label="Parent PBI">
                              {renderTechnicalText(
                                defectResult.output?.adoParentId || adoParentStoryId || '-'
                              )}
                            </td>
                            <td data-label="Open Azure DevOps Bug Link">
                              {defectResult.output?.adoBugUrl ? (
                                <a
                                  href={defectResult.output.adoBugUrl}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  Open Azure DevOps Bug
                                </a>
                              ) : (
                                '-'
                              )}
                            </td>
                          </tr>
                        )
                      })
                    ) : (
                      <tr>
                        <td colSpan={5}>No Azure DevOps bugs have been created yet.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              <div className="report-insight-grid">
                <div className="report-insight-card risk">
                  <span className="scenario-section-label">Risk / Observation</span>
                  <ul>
                    <li>Product defects block QA sign-off.</li>
                    <li>Automation issues should be reviewed by automation team.</li>
                    <li>Environment issues should be reviewed by environment/support team.</li>
                    <li>Needs Review items require manual QA validation.</li>
                  </ul>
                </div>
                <div className="report-insight-card recommendation">
                  <span className="scenario-section-label">QA Recommendation</span>
                  <strong>{finalQaRecommendation}</strong>
                </div>
              </div>

              <div className="report-email-card">
                <div className="report-card-header">
                  <span className="scenario-section-label">Email-style Sign-off Text</span>
                  <strong>Subject: QA Sign-off Summary - {selectedExecutionName}</strong>
                </div>
                <pre>{finalReportEmailText}</pre>
              </div>

              <div className="report-action-row">
                <button type="button" onClick={() => void handleCopyText(finalReportEmailText)}>
                  Copy QA Report Email
                </button>
                <button type="button" onClick={handleDownloadReportHtml}>
                  Download Final QA Report as HTML
                </button>
                <button type="button" onClick={handlePrintReport}>
                  Download Final QA Report as PDF
                </button>
                <button type="button" onClick={handlePrintReport}>
                  Print Report
                </button>
                <button type="button" onClick={() => void handleCopyText(reportSummaryText)}>
                  Copy Summary
                </button>
                <button type="button" onClick={handleShowFinalReportEmailForm}>
                  Prepare QA Report Email
                </button>
              </div>
            </div>
          )}
        </section>

        <section
          className="dashboard-card execution-step-card send-report-email-section"
          data-section="sendQaReportEmail"
        >
          {renderExecutionStepHeader(
            8,
            'Send QA Report Email',
            'Send the final QA sign-off report to stakeholders through Gmail/UiPath Integration Service.',
            emailStepStatus
          )}

          {!finalReportGeneratedAt && (
            <p className="readiness-helper">
              Generate the Final QA Report before preparing the stakeholder email.
            </p>
          )}

          {finalReportGeneratedAt && !showFinalReportEmailForm && (
            <div className="section-action-row">
              <button type="button" onClick={handleShowFinalReportEmailForm}>
                Prepare QA Report Email
              </button>
            </div>
          )}

              {showFinalReportEmailForm && (
                <div className="report-email-form">
                  <div className="report-card-header">
                    <span className="scenario-section-label">Send Final QA Report Email</span>
                    <strong>{finalReportEmailSending ? 'Sending...' : 'Ready to send'}</strong>
                  </div>

                  <div className="report-email-form-grid">
                    <label>
                      To <span>*</span>
                      <input
                        type="email"
                        value={finalReportEmailTo}
                        onChange={(event) => setFinalReportEmailTo(event.target.value)}
                        placeholder="qa-stakeholders@example.com"
                      />
                    </label>
                    <label>
                      CC
                      <input
                        type="text"
                        value={finalReportEmailCc}
                        onChange={(event) => setFinalReportEmailCc(event.target.value)}
                        placeholder="release-owner@example.com"
                      />
                    </label>
                    <label className="report-email-subject-field">
                      Subject
                      <input
                        type="text"
                        value={finalReportEmailSubject}
                        onChange={(event) => setFinalReportEmailSubject(event.target.value)}
                        placeholder={defaultFinalReportEmailSubject}
                      />
                    </label>
                  </div>

                  <label className="report-email-preview-field">
                    Message Preview
                    <textarea value={finalReportEmailText} readOnly rows={12} />
                  </label>

                  {finalReportEmailMessage && (
                    <div className="result-box completed report-email-status">
                      <strong>Email status</strong>
                      <p>{finalReportEmailMessage}</p>
                    </div>
                  )}

                  {finalReportEmailError && (
                    <div className="result-box error report-email-status">
                      <strong>Email failed</strong>
                      <p>{finalReportEmailError}</p>
                    </div>
                  )}

                  {finalReportEmailResult?.message && !finalReportEmailError && (
                    <p className="readiness-helper">
                      {sanitizeUserFacingText(finalReportEmailResult.message)}
                    </p>
                  )}

                  <div className="report-action-row">
                    <button
                      type="button"
                      onClick={handleSendFinalReportEmail}
                      disabled={finalReportEmailSending || !finalReportEmailTo.trim()}
                    >
                      {finalReportEmailSending ? 'Sending QA Report Email...' : 'Send QA Report Email'}
                    </button>
                  </div>
                </div>
              )}
        </section>
      </div>
    </section>
  )

  const releaseReadinessContent = (
    <section className="dashboard-card release-readiness-section" data-section="executionReadiness">
      <div className="section-header">
        <div>
          <span className="small-label">Final Decision Panel</span>
          <h3>Release Readiness</h3>
          <p>Consolidated QA readiness summary from the current workflow run.</p>
        </div>
      </div>

      <div className="final-readiness-card">
        <div className="final-readiness-header">
          <div>
            <span className="small-label">Workflow Summary</span>
            <h4>QualityOps Workflow Readiness</h4>
          </div>
          <span className={`readiness-status-badge ${workflowReadinessBadgeClass}`}>
            {workflowReadinessStatus}
          </span>
        </div>

        <div className="final-readiness-grid">
          <div className="summary-item">
            <span>Requirement Analysis</span>
            <strong>{requirementAnalysisSummaryStatus}</strong>
          </div>
          <div className="summary-item">
            <span>Requirement Review</span>
            <strong>{qaReviewDecision}</strong>
          </div>
          <div className="summary-item">
            <span>Test Scenarios</span>
            <strong>{generatedScenarioCount}</strong>
          </div>
          <div className="summary-item">
            <span>Azure DevOps Test Cases</span>
            <strong>{adoTestCaseCount}</strong>
          </div>
          <div className="summary-item">
            <span>Risk-Based Plan</span>
            <strong>{riskPlanSummaryStatus}</strong>
          </div>
          <div className="summary-item">
            <span>Execution Readiness</span>
            <strong>{executionReadinessSummaryStatus}</strong>
          </div>
          <div className="summary-item">
            <span>UiPath Test Manager Sync</span>
            <strong>{testManagerSyncSummaryStatus}</strong>
          </div>
          <div className="summary-item final-recommendation-item">
            <span>Final Recommendation</span>
            <strong>{finalRecommendation}</strong>
          </div>
        </div>
      </div>

      <div className="readiness-grid">
        <div className="summary-item">
          <span>Requirement Risk</span>
          <strong>{agentOutput?.qaAnalysisSummary?.riskLevel || '-'}</strong>
        </div>
        <div className="summary-item">
          <span>Total Generated Scenarios</span>
          <strong>{generatedScenarioCount}</strong>
        </div>
        <div className="summary-item">
          <span>Total Azure DevOps Test Cases Created</span>
          <strong>{adoTestCaseCount}</strong>
        </div>
        <div className="summary-item" data-section="riskBasedPlan">
          <span>Risk-Based Plan Status</span>
          <strong>{riskPlanOutput?.planningStatus || (isGeneratingRiskPlan ? 'Running' : '-')}</strong>
        </div>
        <div className="summary-item">
          <span>Release Recommendation</span>
          <strong>{riskPlanOutput?.releaseRecommendation || '-'}</strong>
        </div>
        <div className="summary-item">
          <span>Execution Readiness</span>
          <strong>{executionReadinessOutput?.executionReadinessStatus || '-'}</strong>
        </div>
        <div className="summary-item">
          <span>Recommended Test Set</span>
          <strong>{executionReadinessOutput?.recommendedTestSet || '-'}</strong>
        </div>
        <div className="summary-item">
          <span>Execution Mode</span>
          <strong>{executionReadinessOutput?.executionMode || '-'}</strong>
        </div>
        <div className="summary-item">
          <span>Next Action</span>
          <strong>{renderTechnicalText(executionReadinessOutput?.nextAction)}</strong>
        </div>
      </div>

      <div className="test-manager-release-summary">
        <div className="section-header compact-section-header">
          <div>
            <span className="small-label">UiPath Test Manager Sync Summary</span>
            <h4>UiPath Test Manager</h4>
          </div>
        </div>

        <div className="readiness-grid test-manager-release-grid">
          <div className="summary-item">
            <span>Sync Status</span>
            <strong>
              {testManagerWriteBackOutput ? (
                <span className={`readiness-status-badge ${testManagerSyncStatusClass}`}>
                  {testManagerSyncStatusLabel}
                </span>
              ) : (
                '-'
              )}
            </strong>
          </div>
          <div className="summary-item">
            <span>Sync Mode</span>
            <strong>
              {testManagerWriteBackOutput ? testManagerWriteBackOutput.syncMode || '-' : '-'}
            </strong>
          </div>
          <div className="summary-item">
            <span>Test Manager Project</span>
            <strong>{testManagerWriteBackOutput?.testManagerProjectKey || '-'}</strong>
          </div>
          <div className="summary-item">
            <span>Test Cases Prepared</span>
            <strong>{testManagerWriteBackOutput?.summary?.testCasesPrepared ?? 0}</strong>
          </div>
          <div className="summary-item">
            <span>Test Set Prepared</span>
            <strong>{testManagerWriteBackOutput?.testSetPayload?.name || '-'}</strong>
          </div>
          <div className="summary-item">
            <span>Next Action</span>
            <strong>{renderTechnicalText(testManagerWriteBackOutput?.nextAction)}</strong>
          </div>
        </div>
      </div>

      {executionReadinessOutput?.blockedReasons?.length ? (
        <div className="blocked-reasons-panel release-readiness-blockers">
          <span className="scenario-section-label">Execution Readiness Blocked Reasons</span>
          <ul className="compact-list">
            {executionReadinessOutput.blockedReasons.map((reason, index) => (
              <li key={`${reason}-${index}`}>{renderTechnicalText(reason)}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="section-action-row">
        <button
          className="generate-button"
          onClick={handleGenerateRiskPlan}
          disabled={isGeneratingRiskPlan || !generatedScenarios.length}
        >
          {isGeneratingRiskPlan ? 'Generating Risk-Based Plan...' : 'Generate Risk-Based Execution Plan'}
        </button>
        <button
          className="readiness-button"
          onClick={handleCheckExecutionReadiness}
          disabled={isCheckingExecutionReadiness || !canCheckExecutionReadiness}
        >
          {isCheckingExecutionReadiness ? 'Checking Execution Readiness...' : 'Check Execution Readiness'}
        </button>
      </div>

      <div className={`result-box ${isCheckingExecutionReadiness ? 'running' : status.toLowerCase()}`}>
        <strong>{riskPlanOutput?.planningStatus || 'Awaiting risk-based execution plan'}</strong>
        <p>
          {isGeneratingRiskPlan || isCheckingExecutionReadiness
            ? displayStatusMessage
            : sanitizeUserFacingText(riskPlanOutput?.releaseRecommendation || statusMessage)}
        </p>
      </div>

      {riskPlanOutput && (
        <div className="risk-plan-output">
          <div className="coverage-summary-grid">
            <div className="summary-item">
              <span>Functional</span>
              <strong>{riskPlanOutput.coverageSummary?.functional ?? 0}</strong>
            </div>
            <div className="summary-item">
              <span>Negative</span>
              <strong>{riskPlanOutput.coverageSummary?.negative ?? 0}</strong>
            </div>
            <div className="summary-item">
              <span>Integration</span>
              <strong>{riskPlanOutput.coverageSummary?.integration ?? 0}</strong>
            </div>
            <div className="summary-item">
              <span>Regression</span>
              <strong>{riskPlanOutput.coverageSummary?.regression ?? 0}</strong>
            </div>
            <div className="summary-item">
              <span>Edge Case</span>
              <strong>{riskPlanOutput.coverageSummary?.edgeCase ?? 0}</strong>
            </div>
            <div className="summary-item">
              <span>Total</span>
              <strong>{riskPlanOutput.coverageSummary?.total ?? 0}</strong>
            </div>
          </div>

          <div className="release-recommendation-card">
            <span className="scenario-section-label">Release Recommendation</span>
            <p>{riskPlanOutput.releaseRecommendation || '-'}</p>
          </div>

          {riskPlanOutput.recommendedExecutionOrder?.length ? (
            <div className="risk-plan-table-wrap">
              <table className="risk-plan-table">
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Scenario</th>
                    <th>Priority</th>
                    <th>Test Type</th>
                    <th>Execution</th>
                    <th>Risk Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {riskPlanOutput.recommendedExecutionOrder.map((item, index) => (
                    <tr key={`${item.scenarioId || 'risk-plan'}-${index}`}>
                      <td data-label="Rank">{item.rank ?? index + 1}</td>
                      <td data-label="Scenario">
                        <strong>{getDisplayScenarioTitle(item, index)}</strong>
                        {item.scenarioId ? <span>Key: {item.scenarioId}</span> : null}
                      </td>
                      <td data-label="Priority">{item.priority || '-'}</td>
                      <td data-label="Test Type">{item.testType || '-'}</td>
                      <td data-label="Execution">{item.executionType || '-'}</td>
                      <td data-label="Risk Reason">{renderTechnicalText(item.riskReason)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="empty-scenarios">No recommended execution order was returned.</p>
          )}

          {riskPlanOutput.failedScenarios?.length ? (
            <div className="failed-scenario-summary risk-failure-summary">
              <span className="scenario-section-label">Failed Scenarios</span>
              <div className="failed-scenario-grid">
                {riskPlanOutput.failedScenarios.map((scenario, index) => (
                  <article className="failed-scenario-card" key={`${scenario.scenarioId || 'risk-failed'}-${index}`}>
                    <strong>{scenario.scenarioId || `Scenario ${index + 1}`}</strong>
                    <p>
                      {scenario.scenarioTitle ||
                        scenario.title ||
                        scenario.errorMessage ||
                        scenario.reason ||
                        'Planning failed'}
                    </p>
                  </article>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      )}
    </section>
  )

  const activityTimestamp = finalReportGeneratedAt || executionHistory[0]?.timestamp || 'Current session'
  const workflowActivityHistory = [
    agentOutput && {
      activityName: 'Requirement analysis',
      status: 'Completed',
      parentId: requirementId || adoParentStoryId || '-',
      timestamp: executionHistory[0]?.timestamp || activityTimestamp,
      summary:
        agentOutput.requirementQualityAnalysis?.approvalRecommendation ||
        agentOutput.qaAnalysisSummary?.nextStep ||
        'Requirement analysis completed.',
      artifactCount: agentOutput.requirementQualityAnalysis?.identifiedGaps?.length ?? 0,
      artifactLabel: 'identified gaps',
    },
    qaLeadReview && {
      activityName: 'Requirement Review',
      status:
        qaLeadReview.decision === 'Approve'
          ? 'Approved'
          : qaLeadReview.decision === 'Reject'
            ? 'Rejected'
            : 'Needs Changes',
      parentId: requirementId || adoParentStoryId || '-',
      timestamp: qaLeadReview.createdAt,
      summary: adoCommentAdded
        ? 'QA Lead review saved and written back to Azure DevOps.'
        : 'QA Lead review feedback saved and passed as workflow memory.',
      artifactCount: 1,
      artifactLabel: 'review memory',
    },
    testGenerationResult && {
      activityName: 'Test scenario generation',
      status: testGenerationResult.generationStatus || 'Completed',
      parentId: requirementId || adoParentStoryId || '-',
      timestamp: activityTimestamp,
      summary: 'Generated QA scenarios from reviewed requirement analysis.',
      artifactCount: generatedScenarios.length,
      artifactLabel: 'scenarios',
    },
    testCaseWriteBackOutput && {
      activityName: 'Azure DevOps test case creation',
      status: testCaseWriteBackOutput.writeBackStatus || 'Completed',
      parentId: adoParentStoryId || requirementId || '-',
      timestamp: activityTimestamp,
      summary: 'Created Azure DevOps Test Case work items from generated scenarios.',
      artifactCount: testCaseWriteBackOutput.createdTestCases?.length ?? 0,
      artifactLabel: 'test cases',
    },
    testManagerWriteBackOutput && {
      activityName: 'UiPath Test Manager sync',
      status: testManagerSyncStatusLabel,
      parentId: adoParentStoryId || requirementId || '-',
      timestamp: activityTimestamp,
      summary: testManagerWriteBackOutput.nextAction || 'Synced QA artifacts to UiPath Test Manager.',
      artifactCount: latestAllTestCaseIds.length || latestAutomationLinkTestCaseIds.length,
      artifactLabel: 'Test Manager test cases',
      link: testManagerTestSetUrl,
      linkLabel: 'Open Test Set',
    },
    automationLinkResult && {
      activityName: 'Automation mapping',
      status: automationLinkResult.automationLinkStatus || 'Completed',
      parentId: adoParentStoryId || requirementId || '-',
      timestamp: activityTimestamp,
      summary: 'Mapped UiPath Test Manager test cases to automated package entry points.',
      artifactCount: automationLinkResult.linkedCount ?? automationLinkResult.linkedMappings?.length ?? 0,
      artifactLabel: 'mapped tests',
      link: testManagerTestSetUrl,
      linkLabel: 'Open Test Set',
    },
    triageAnalysisResult && {
      activityName: 'Test result triage',
      status: getTriageStatus(triageAnalysisResult) || 'Completed',
      parentId: adoParentStoryId || requirementId || '-',
      timestamp: activityTimestamp,
      summary: getTriageOverallRecommendation(triageAnalysisResult) || 'Analyzed UiPath Test Manager execution results.',
      artifactCount: failedTriageResults.length,
      artifactLabel: 'failed results',
      link: testManagerExecutionLink,
      linkLabel: 'Open Evidence',
    },
    defectCreationResults.length > 0 && {
      activityName: 'Azure DevOps bug creation',
      status: defectCreationResults.some((item) => item.status === 'Failed') ? 'Needs Attention' : 'Completed',
      parentId: adoParentStoryId || requirementId || '-',
      timestamp: activityTimestamp,
      summary: 'Created Azure DevOps Bugs from selected failed tests.',
      artifactCount: createdAdoBugs.length,
      artifactLabel: 'bugs',
      link: createdAdoBugs[0],
      linkLabel: 'Open Bug',
    },
    finalReportGeneratedAt && {
      activityName: 'Final QA report generation',
      status: 'Completed',
      parentId: adoParentStoryId || requirementId || '-',
      timestamp: finalReportGeneratedAt,
      summary: finalQaRecommendation,
      artifactCount: 1,
      artifactLabel: 'report',
    },
    finalReportEmailSent && {
      activityName: 'Final QA report email sent',
      status: finalReportEmailResult?.emailStatus || finalReportEmailResult?.mailStatus || 'Completed',
      parentId: adoParentStoryId || requirementId || '-',
      timestamp: activityTimestamp,
      summary: finalReportEmailResult?.message || `Sent to ${finalReportEmailTo || 'stakeholders'}.`,
      artifactCount: 1,
      artifactLabel: 'email',
    },
  ].filter(Boolean) as Array<{
    activityName: string
    status: string
    parentId: string
    timestamp: string
    summary: string
    artifactCount: number
    artifactLabel: string
    link?: string
    linkLabel?: string
  }>

  const getStatusClassName = (value: string) => {
    const normalizedValue = value.toLowerCase()

    if (normalizedValue.includes('complete') || normalizedValue.includes('ready') || normalizedValue.includes('approved')) {
      return 'status-completed'
    }

    if (normalizedValue.includes('fail') || normalizedValue.includes('error') || normalizedValue.includes('bug')) {
      return 'status-failed'
    }

    if (normalizedValue.includes('attention') || normalizedValue.includes('warning') || normalizedValue.includes('action')) {
      return 'status-warning'
    }

    return 'status-pending'
  }

  const getStepStatus = (stepKey: string): ExecutionStepStatus => {
    const step = workflowSteps.find((item) => item.label === stepKey)

    if (!step) {
      return 'Pending'
    }

    if (step.status === 'Completed') {
      return 'Completed'
    }

    if (step.status === 'Error') {
      return 'Failed'
    }

    if (step.status === 'Warning') {
      return 'Needs Attention'
    }

    return status === 'Running' && actionType === 'Test Execution' ? 'In Progress' : 'Pending'
  }

  const getApprovedCount = () => testCaseReviewCounts.approved
  const getAutomationCoverage = () =>
    automationLinkResult
      ? '100%'
      : testManagerWriteBackOutput?.syncStatus === 'Completed'
        ? '0%'
        : '-'
  const getExecutionPassRate = () => {
    const passed = triageExecutionSummary?.passed ?? 0
    const total =
      triageExecutionSummary?.totalTests ??
      ((triageExecutionSummary?.passed ?? 0) +
        (triageExecutionSummary?.failed ?? 0) +
        (triageExecutionSummary?.skipped ?? 0))

    return total > 0 ? `${Math.round((passed / total) * 100)}%` : '-'
  }
  const getOpenBugCount = () => createdAdoBugs.length
  const getWorkflowStatus = () =>
    workflowReadinessStatus === 'Ready'
      ? 'Completed'
      : status === 'Running'
        ? 'In Progress'
        : 'Action Required'
  const getRecentActivities = () => workflowActivityHistory.slice(0, 8)
  const getReleaseReadinessStatus = () =>
    workflowReadinessStatus === 'Ready' ? 'Ready for Release' : 'Action Required'
  const executionSummaryTotals = {
    total: triageExecutionSummary?.totalTests ?? 0,
    passed: triageExecutionSummary?.passed ?? 0,
    failed: triageExecutionSummary?.failed ?? failedTriageResults.length,
    blocked: triageExecutionSummary?.skipped ?? 0,
  }
  const moduleProgressItems = [
    ['Requirement Analysis', isRequirementAnalysisCompleted ? 100 : 0],
    ['Requirement Review', isRequirementReviewCompleted ? 100 : 0],
    ['Test Generation', isTestGenerationCompleted ? 100 : 0],
    ['Test Execution', isAnalyzeTestResultsCompleted ? 100 : isAutomationMappingCompleted ? 65 : isTestManagerSyncCompleted ? 45 : 0],
    ['Release Readiness', workflowReadinessStatus === 'Ready' ? 100 : isRiskPlanCompleted ? 60 : 0],
  ] as Array<[string, number]>
  const bugStatusCounts = {
    high: failedTriageResults.filter((item) => getDisplayClassification(item) === 'Product Defect').length,
    medium: failedTriageResults.filter((item) => getDisplayClassification(item) === 'Automation Issue').length,
    low: failedTriageResults.filter((item) => !['Product Defect', 'Automation Issue'].includes(getDisplayClassification(item))).length,
    resolved: defectCreationResults.filter((item) => item.status === 'Completed').length,
  }
  const dashboardStepCards = [
    { stepKey: 'requirementAnalysis', number: '1', title: 'Requirement Analysis', status: getStepStatus('Requirement Analysis') },
    { stepKey: 'requirementReview', number: '2', title: 'Requirement Review', status: getStepStatus('Requirement Review') },
    { stepKey: 'testGeneration', number: '3', title: 'Test Generation', status: getStepStatus('Test Generation') },
    { stepKey: 'azureDevOpsSync', number: '4', title: 'Azure DevOps Sync', status: getStepStatus('Azure DevOps Sync') },
    { stepKey: 'riskBasedPlan', number: '5', title: 'Risk-Based Plan', status: getStepStatus('Risk-Based Plan') },
    { stepKey: 'executionReadiness', number: '6', title: 'Execution Readiness', status: getStepStatus('Execution Readiness') },
    { stepKey: 'testManagerSync', number: '7', title: 'Test Manager Sync', status: getStepStatus('Test Manager Sync') },
    { stepKey: 'automationMapping', number: '8', title: 'Map Automated Test Cases', status: getStepStatus('Map Automated Test Cases') },
    { stepKey: 'testResultTriage', number: '9', title: 'Analyze Test Results', status: getStepStatus('Analyze Test Results') },
    { stepKey: 'bugCreation', number: '10', title: 'Create Azure DevOps Bug', status: getStepStatus('Create Azure DevOps Bug') },
    { stepKey: 'finalQaReport', number: '11', title: 'Generate Final QA Report', status: getStepStatus('Generate Final QA Report') },
    { stepKey: 'sendQaReportEmail', number: '12', title: 'Send QA Report Email', status: getStepStatus('Send QA Report Email') },
  ] as Array<{
    stepKey:
      | 'requirementAnalysis'
      | 'requirementReview'
      | 'testGeneration'
      | 'azureDevOpsSync'
      | 'riskBasedPlan'
      | 'executionReadiness'
      | 'testManagerSync'
      | 'automationMapping'
      | 'testResultTriage'
      | 'bugCreation'
      | 'finalQaReport'
      | 'sendQaReportEmail'
    number: string
    title: string
    status: ExecutionStepStatus
  }>

  const scrollToSection = (sectionKey: string) => {
    window.setTimeout(() => {
      document
        .querySelector<HTMLElement>(`[data-section="${sectionKey}"]`)
        ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 120)
  }

  const handleDashboardStepClick = (stepKey: string) => {
    switch (stepKey) {
      case 'requirementAnalysis':
        setActiveSidebarSection('requirement-analysis')
        break
      case 'requirementReview':
        setActiveSidebarSection('requirement-review')
        break
      case 'testGeneration':
        setActiveSidebarSection('test-generation')
        break
      case 'azureDevOpsSync':
        setActiveSidebarSection('test-execution')
        scrollToSection('azureDevOpsSync')
        break
      case 'riskBasedPlan':
        console.log('Dashboard step clicked:', stepKey, 'navigating to Release Readiness')
        setActiveSidebarSection('release-readiness')
        window.setTimeout(() => {
          document
            .querySelector<HTMLElement>('[data-section="riskBasedPlan"]')
            ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }, 300)
        break
      case 'executionReadiness':
        setActiveSidebarSection('release-readiness')
        scrollToSection('executionReadiness')
        break
      case 'testManagerSync':
        setActiveSidebarSection('test-execution')
        scrollToSection('testManagerSync')
        break
      case 'automationMapping':
        setActiveSidebarSection('test-execution')
        scrollToSection('automationMapping')
        break
      case 'testResultTriage':
        setActiveSidebarSection('test-execution')
        scrollToSection('testResultTriage')
        break
      case 'bugCreation':
        setActiveSidebarSection('test-execution')
        scrollToSection('bugCreation')
        break
      case 'finalQaReport':
        setActiveSidebarSection('test-execution')
        scrollToSection('finalQaReport')
        break
      case 'sendQaReportEmail':
        setActiveSidebarSection('test-execution')
        scrollToSection('sendQaReportEmail')
        break
    }
  }

  const executionHistoryContent = (
    <section className="history-panel">
      <div className="panel-header">
        <h3>Execution History</h3>
        <p>Recent QualityOps workflow activity from this session.</p>
      </div>

      {workflowActivityHistory.length === 0 ? (
        <div className="empty-history">
          No execution history available yet. Run the QualityOps workflow to see recent activity here.
        </div>
      ) : (
        <div className="history-card-list">
          {workflowActivityHistory.map((item, index) => (
            <article className="history-card" key={`${item.activityName}-${item.timestamp}-${index}`}>
              <div className="history-card-header">
                <div>
                  <span className="small-label">Activity</span>
                  <strong>{item.activityName}</strong>
                </div>

                <span className="history-status">{item.status}</span>
              </div>

              <div className="history-details">
                <div>
                  <span>Parent PBI / Requirement ID</span>
                  <strong>{renderTechnicalText(item.parentId)}</strong>
                </div>

                <div>
                  <span>Created Artifacts</span>
                  <strong>
                    {item.artifactCount} {item.artifactLabel}
                  </strong>
                </div>

                <div>
                  <span>Timestamp</span>
                  <strong>{item.timestamp}</strong>
                </div>
              </div>

              <div className="history-next-step">
                <span>Summary</span>
                <p>{renderTechnicalText(item.summary)}</p>
              </div>

              {item.link && (
                <div className="history-footer">
                  <a href={item.link} target="_blank" rel="noreferrer">
                    {item.linkLabel || 'Open Link'}
                  </a>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  )

  return (
    <main className="app-shell qualityops-shell main-layout qualityops-app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">Q</div>
          <div>
            <h1>QualityOps</h1>
            <p>QA Console</p>
          </div>
        </div>

        <nav className="nav-list" aria-label="QualityOps sections">
          {navigationItems.map((item) => (
            <button
              key={item.label}
              className={`nav-item ${activeSidebarSection === item.sectionId ? 'active' : ''}`}
              onClick={() => setActiveSidebarSection(item.sectionId)}
              aria-current={activeSidebarSection === item.sectionId ? 'page' : undefined}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-card">
          <strong>QUALITYOPS FLOW</strong>
          <p>End-to-end QA workflow from requirement analysis to final QA sign-off report.</p>
        </div>
      </aside>

      <section className="main-content page-content">
        <div className="qo-dashboard-v2">
          {activeSidebarSection === 'dashboard' && (
            <section>
              <header className="qo-hero">
                <div>
                  <span className="eyebrow">AI-powered QA workflow console</span>
                  <h2>QualityOps QA Console</h2>
                  <p>
                    One interface for requirement review, test generation, execution, final QA
                    reporting, and release readiness.
                  </p>
                </div>

                <div className="dashboard-header-actions">
                  <label>
                    Environment
                    <select value={environment} onChange={(event) => setEnvironment(event.target.value)}>
                      <option>DEV</option>
                      <option>SQA</option>
                      <option>UAT</option>
                      <option>Production</option>
                    </select>
                  </label>
                  <button className="logout-button" onClick={logout}>
                    Logout
                  </button>
                </div>
              </header>

              <div className="qo-kpi-grid">
                {[
                  ['MOD', 'Total Modules', '5', 'Requirement to release readiness'],
                  ['ACT', 'Active Module', actionType || 'Release Readiness', 'Current focused workflow'],
                  ['ENV', 'Environment', environment || 'SQA', 'Selected execution target'],
                  ['QA', 'QA Status', getWorkflowStatus(), 'Current workflow state'],
                  ['TC', 'Approved Test Cases', String(getApprovedCount()), 'Total approved for execution'],
                  ['AUTO', 'Automation Coverage', getAutomationCoverage(), 'Mapped to automated tests'],
                  ['PASS', 'Execution Pass Rate', getExecutionPassRate(), 'Passed / Total executed'],
                  ['BUG', 'Open Bugs', String(getOpenBugCount()), 'Open bugs in Azure DevOps'],
                ].map(([icon, label, value, helper]) => (
                  <article className="qo-kpi-card" key={label}>
                    <div className="kpi-icon">{icon}</div>
                    <div>
                      <span className="qo-kpi-title">{label}</span>
                      <strong className="qo-kpi-value">{value}</strong>
                      <p className="qo-kpi-helper">{helper}</p>
                    </div>
                  </article>
                ))}
              </div>

              {workflowRunner}

              <section className="qo-step-grid" aria-label="QualityOps workflow steps">
                {dashboardStepCards.map((step) => (
                  <button
                    key={step.title}
                    type="button"
                    className="qo-step-card"
                    role="button"
                    tabIndex={0}
                    onClick={() => handleDashboardStepClick(step.stepKey)}
                    aria-label={`Open ${step.title}`}
                  >
                    <span className={`step-number ${getStatusClassName(step.status)}`}>{step.number}</span>
                    <div>
                      <strong className="qo-step-title">{step.title}</strong>
                      <span className={`qo-step-status ${getStatusClassName(step.status)}`}>
                        {step.status}
                      </span>
                    </div>
                  </button>
                ))}
              </section>

              <section className="qo-activity-card">
                <div className="panel-header">
                  <h3>Recent Activity</h3>
                  <p>Latest workflow events in the current run.</p>
                </div>
                {getRecentActivities().length ? (
                  <div className="activity-list">
                    {getRecentActivities().map((item, index) => (
                      <article className="activity-row" key={`${item.activityName}-${index}`}>
                        <span className={`activity-dot ${getStatusClassName(item.status)}`} />
                        <div>
                          <strong>{item.activityName}</strong>
                          <p>{renderTechnicalText(item.summary)}</p>
                        </div>
                        <time>{item.timestamp || 'Current run'}</time>
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="empty-scenarios">
                    No activity yet. Run a workflow action to populate this panel.
                  </p>
                )}
              </section>

              <div className="qo-summary-grid">
                <section className="qo-summary-card">
                  <span className="small-label">Test Execution Summary</span>
                  <div className="summary-metric-row">
                    <strong>{executionSummaryTotals.total}</strong><span>Total executed</span>
                  </div>
                  <div className="summary-mini-grid">
                    <span>Passed: {executionSummaryTotals.passed}</span>
                    <span>Failed: {executionSummaryTotals.failed}</span>
                    <span>Blocked: {executionSummaryTotals.blocked}</span>
                  </div>
                </section>

                <section className="qo-summary-card">
                  <span className="small-label">Module Completion</span>
                  <div className="module-progress-list">
                    {moduleProgressItems.map(([label, percent]) => (
                      <div className="module-progress-row" key={label}>
                        <span>{label}</span>
                        <div><span style={{ width: `${percent}%` }} /></div>
                        <strong>{percent}%</strong>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="qo-summary-card">
                  <span className="small-label">Bug Status</span>
                  <div className="bug-status-grid">
                    <span>High <strong>{bugStatusCounts.high}</strong></span>
                    <span>Medium <strong>{bugStatusCounts.medium}</strong></span>
                    <span>Low <strong>{bugStatusCounts.low}</strong></span>
                    <span>Resolved <strong>{bugStatusCounts.resolved}</strong></span>
                  </div>
                </section>

                <section className="qo-summary-card release-summary-card">
                  <span className="small-label">Release Readiness</span>
                  <strong>{getReleaseReadinessStatus()}</strong>
                  <p>
                    {workflowReadinessStatus === 'Ready'
                      ? 'All quality gates passed.'
                      : 'Complete pending workflow steps before release sign-off.'}
                  </p>
                </section>
              </div>
            </section>
          )}

          {activeSidebarSection === 'requirement-analysis' && requirementAnalysisContent}
          {activeSidebarSection === 'requirement-review' && requirementReviewContent}
          {activeSidebarSection === 'test-generation' && testGenerationContent}
          {activeSidebarSection === 'test-execution' && testExecutionContent}
          {activeSidebarSection === 'release-readiness' && releaseReadinessContent}
          {activeSidebarSection === 'execution-history' && executionHistoryContent}
        </div>
      </section>
    </main>
  )
}

function App() {
  return (
    <AuthProvider config={authConfig}>
      <AppContent />
    </AuthProvider>
  )
}

export default App
