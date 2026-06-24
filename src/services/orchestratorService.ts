type RequirementAgentInput = {
  requirementId: string
  submittedBy: string
  environment: string
}

export type RequirementAgentOutput = {
  processingStatus?: string
  requirementTitle?: string
  requirementDescription?: string
  acceptanceCriteria?: string
  adoUpdateStatus?: string
  qaLeadNotificationRequired?: boolean
  qaAnalysisSummary?: {
    impactedModules?: string[]
    changeType?: string
    riskLevel?: string
    testingScope?: string[]
    suggestedTestFocus?: string[]
    humanReviewRequired?: boolean
    nextStep?: string
  }
  requirementQualityAnalysis?: {
    readinessStatus?: string
    readinessScore?: number
    identifiedGaps?: string[]
    ragChecklistUsed?: string[]
    qaLeadActionRequired?: boolean
    approvalRecommendation?: string
    qaLeadDecisionStatus?: string
  }
}

export type RequirementAgentRunResult = {
  processingStatus: string
  jobId?: number
  jobKey?: string
  jobState?: string
  output?: RequirementAgentOutput
  raw?: unknown
}

export type AdoWriteBackInput = {
  mode?: 'writeRequirementReviewComment'
  requirementId: string
  decisionType?: string
  decisionComment?: string
  submittedBy: string
  environment: string
  commentTitle?: string
  qaLeadReview?: QaLeadReview
  commentHtml?: string
}

export type AdoWriteBackOutput = {
  status?: string
  writeBackStatus?: string
  requirementId?: string
  decisionType?: string
  commentText?: string
  errorMessage?: string
  message?: string
  blockedReasons?: string[]
}

export type AdoWriteBackRunResult = {
  processingStatus: string
  jobId?: number
  jobKey?: string
  jobState?: string
  output?: AdoWriteBackOutput
  raw?: unknown
}

export type QaLeadReview = {
  requirementId: string
  requirementTitle: string
  decision: string
  feedbackCategory: string
  feedbackText: string
  originalRiskLevel: string
  originalReadinessStatus: string
  originalReadinessScore: string
  originalIdentifiedGaps: string[]
  originalSuggestedTestFocus: string[]
  submittedBy: string
  createdAt: string
}

export type TestScenarioGenerationInput = {
  requirementId: string
  submittedBy: string
  environment: string
  requirementAnalysis?: RequirementAgentOutput
  qaLeadReview?: QaLeadReview
  requirementTitle?: string
  requirementDescription?: string
  acceptanceCriteria?: string
  riskLevel?: string
  testingScope?: string[]
  suggestedTestFocus?: string[]
}

export type TestCaseStep = string | {
  action?: string
  description?: string
  expected?: string
  expectedResult?: string
  result?: string
  step?: string
}

export type TestScenario = {
  scenarioKey?: string
  scenarioId?: string
  scenarioTitle?: string
  title?: string
  name?: string
  description?: string
  summary?: string
  priority?: string
  testType?: string
  type?: string
  preconditions?: string[]
  steps?: TestCaseStep[]
  expectedResult?: string
  adoStepsXml?: string
  reviewStatus?: string
  reviewComment?: string
  reviewedBy?: string
  reviewedAt?: string
}

export type TestScenarioGenerationOutput = {
  generationStatus?: string
  generationMode?: string
  llmGenerationUsed?: boolean
  vectorRagStatus?: string
  fallbackRagUsed?: boolean
  ragSourcesUsed?: unknown
  testScenarios?: TestScenario[]
}

export type TestScenarioGenerationRunResult = {
  processingStatus: string
  jobId?: number
  jobKey?: string
  jobState?: string
  output?: TestScenarioGenerationOutput
  raw?: unknown
}

export type AdoTestCaseWriteBackInput = {
  requirementId: string
  submittedBy: string
  environment: string
  testScenarios: TestScenario[]
}

export type CreatedTestCase = {
  scenarioKey?: string
  scenarioId?: string
  testCaseId?: number | string
  adoTestCaseId?: number | string
  id?: number | string
  workItemId?: number | string
  title?: string
  adoUrl?: string
  url?: string
  webUrl?: string
}

export type FailedScenario = {
  scenarioId?: string
  title?: string
  errorMessage?: string
}

export type AdoTestCaseWriteBackOutput = {
  writeBackStatus?: string
  requirementId?: string
  createdTestCases?: CreatedTestCase[]
  failedScenarios?: FailedScenario[]
}

export type AdoTestCaseWriteBackRunResult = {
  processingStatus: string
  jobId?: number
  jobKey?: string
  jobState?: string
  output?: AdoTestCaseWriteBackOutput
  raw?: unknown
}

export type RiskBasedTestPlannerInput = {
  requirementId: string
  submittedBy: string
  environment: string
  requirementTitle?: string
  riskLevel?: string
  testingScope?: string[]
  suggestedTestFocus?: string[]
  testScenarios: TestScenario[]
  createdTestCases?: CreatedTestCase[]
}

export type RecommendedExecutionItem = {
  rank?: number
  scenarioId?: string
  scenarioTitle?: string
  priority?: string
  testType?: string
  executionType?: string
  riskReason?: string
}

export type RiskPlannerCoverageSummary = {
  functional?: number
  negative?: number
  integration?: number
  regression?: number
  edgeCase?: number
  total?: number
}

export type RiskPlannerFailedScenario = {
  scenarioId?: string
  scenarioTitle?: string
  title?: string
  error?: string
  errorMessage?: string
  reason?: string
}

export type RiskBasedTestPlannerOutput = {
  planningStatus?: string
  requirementId?: string
  recommendedExecutionOrder?: RecommendedExecutionItem[]
  coverageSummary?: RiskPlannerCoverageSummary
  releaseRecommendation?: string
  failedScenarios?: RiskPlannerFailedScenario[]
}

export type RiskBasedTestPlannerRunResult = {
  processingStatus: string
  jobId?: number
  jobKey?: string
  jobState?: string
  output?: RiskBasedTestPlannerOutput
  raw?: unknown
}

function trimText(value: unknown, max = 250): string {
  return String(value || '').slice(0, max)
}

function getRiskPlanScenarioTitle(scenario: any, index: number): string {
  return trimText(
    scenario?.testCaseTitle ||
      scenario?.title ||
      scenario?.scenarioTitle ||
      scenario?.name ||
      `Test Case ${index + 1}`,
    120
  )
}

function buildCompactRiskPlanPayload(input: RiskBasedTestPlannerInput) {
  const createdTestCases = input.createdTestCases || []
  const approvedScenarios = (input.testScenarios || []).filter(
    (scenario: any) => (scenario?.reviewStatus || 'Approved') === 'Approved'
  )
  const testScenarios = approvedScenarios.map((scenario: any, index) => {
    const created = createdTestCases[index] as any
    const scenarioTitle = getRiskPlanScenarioTitle(scenario, index)
    const testType = trimText(
      scenario?.testType || scenario?.category || scenario?.type || scenario?.testCategory || 'Functional',
      80
    )

    return {
      scenarioId: trimText(
        scenario?.scenarioKey ||
          scenario?.scenarioId ||
          scenario?.id ||
          `scenario-${index + 1}`,
        120
      ),
      scenarioTitle,
      testType,
      priority: trimText(scenario?.priority || 'Medium', 40),
      riskLevel: trimText(scenario?.riskLevel || scenario?.risk || scenario?.priority || 'Medium', 40),
      reviewStatus: trimText(scenario?.reviewStatus || 'Approved', 40),
      adoTestCaseId: trimText(
        scenario?.adoTestCaseId ||
          scenario?.testCaseId ||
          scenario?.workItemId ||
          created?.adoTestCaseId ||
          created?.id ||
          created?.testCaseId ||
          created?.workItemId ||
          '',
        80
      ),
      module: trimText(
        scenario?.module || scenario?.impactedModule || scenario?.area || '',
        80
      ),
      description: trimText(
        scenario?.description || scenario?.summary || scenarioTitle,
        250
      ),
    }
  })
  const uniqueTestScenarios = Array.from(
    new Map(testScenarios.map((item) => [item.scenarioId, item])).values()
  )

  return {
    operation: 'GENERATE_RISK_BASED_PLAN',
    requirementId: String(input.requirementId || 'latest'),
    instruction:
      'Generate a risk-based execution plan using the provided approved testScenarios. Return valid JSON only.',
    testScenarios: uniqueTestScenarios,
  }
}

export type ExecutionReadinessInput = {
  requirementId: string
  submittedBy: string
  environment: string
  requirementTitle?: string
  riskLevel?: string
  qaReviewStatus?: string
  testScenarioCount: number
  adoTestCaseCreatedCount: number
  riskPlanningStatus?: string
  recommendedExecutionOrder?: RecommendedExecutionItem[]
  coverageSummary?: RiskPlannerCoverageSummary
}

export type TestsToRunFirstItem = {
  rank?: number
  scenarioId?: string
  scenarioTitle?: string
  priority?: string
  testType?: string
}

export type ExecutionReadinessOutput = {
  readinessStatus?: string
  requirementId?: string
  executionReadinessStatus?: string
  recommendedTestSet?: string
  executionMode?: string
  testsToRunFirst?: TestsToRunFirstItem[]
  blockedReasons?: string[]
  nextAction?: string
}

export type ExecutionReadinessRunResult = {
  processingStatus: string
  jobId?: number
  jobKey?: string
  jobState?: string
  output?: ExecutionReadinessOutput
  raw?: unknown
}

export type TestManagerWriteBackInput = {
  requirementId: string
  submittedBy: string
  environment: string
  testManagerProjectKey: string
  testManagerProjectName: string
  requirementTitle?: string
  requirementDescription?: string
  riskLevel?: string
  testScenarios: TestScenario[]
  createdAdoTestCases?: CreatedTestCase[]
  riskBasedPlan: RiskBasedTestPlannerOutput
  syncMode: string
  testSetMode?: string
}

export type TestManagerRequirementPayload = {
  externalId?: string
  name?: string
  description?: string
}

export type TestManagerTestCaseStep = {
  stepNumber?: number
  order?: number
  action?: string
  expectedResult?: string
}

export type TestManagerTestCasePayload = {
  scenarioId?: string
  name?: string
  scenarioTitle?: string
  priority?: string
  testType?: string
  adoTestCaseId?: string | number
  createdTestCaseId?: string | number
  reusedTestCaseId?: string | number
  status?: string
  linkStatus?: string
  membershipStatus?: string
  steps?: TestManagerTestCaseStep[]
}

export type TestManagerTestSetPayload = {
  name?: string
  environment?: string
  description?: string
}

export type TestManagerSummary = {
  requirementsPrepared?: number
  testCasesPrepared?: number
  linksPrepared?: number
  testSetsPrepared?: number
}

export type TestManagerWriteBackOutput = {
  syncStatus?: string
  syncMode?: string
  requirementId?: string
  createdTestCaseIds?: Array<string | number>
  reusedTestCaseIds?: Array<string | number>
  allTestCaseIds?: Array<string | number>
  mappedTestCaseIds?: Array<string | number>
  createdTestSetId?: string | number
  testManagerTestSetId?: string | number
  testSetId?: string | number
  testCaseReuseEnabled?: boolean
  testManagerProjectKey?: string
  requirementPayload?: TestManagerRequirementPayload
  testCasePayloads?: TestManagerTestCasePayload[]
  requirementLinks?: unknown[]
  testSetPayload?: TestManagerTestSetPayload
  testSetMembership?: unknown[]
  summary?: TestManagerSummary
  blockedReasons?: string[]
  nextAction?: string
}

export type TestManagerWriteBackRunResult = {
  processingStatus: string
  jobId?: number
  jobKey?: string
  jobState?: string
  output?: TestManagerWriteBackOutput
  raw?: unknown
}

function buildCompactTestManagerPayload(input: TestManagerWriteBackInput) {
  const approvedScenarios = (input.testScenarios || []).filter(
    (scenario: any) => (scenario?.reviewStatus || 'Approved') === 'Approved'
  )
  const createdAdoTestCases = input.createdAdoTestCases || []
  const createdSource = createdAdoTestCases.length ? createdAdoTestCases : approvedScenarios
  const testScenarios = createdSource.map((testCase: any, index: number) => {
    const approvedScenario = approvedScenarios[index] as any
    const rawScenarioTitle = trimText(
      approvedScenario?.testCaseTitle ||
        approvedScenario?.scenarioTitle ||
        approvedScenario?.title ||
        testCase?.testCaseTitle ||
        testCase?.title ||
        `Test Scenario ${index + 1}`,
      140
    )
    const scenarioTitle = /^TS-\d+/i.test(rawScenarioTitle)
      ? rawScenarioTitle
      : `TS-${String(index + 1).padStart(3, '0')} - ${rawScenarioTitle}`

    return {
      scenarioId: trimText(
        testCase?.scenarioKey ||
          approvedScenario?.scenarioKey ||
          `scenario-${index + 1}`,
        120
      ),
      scenarioTitle,
      testType: trimText(
        testCase?.testType ||
          approvedScenario?.testType ||
          approvedScenario?.category ||
          'Functional',
        80
      ),
      priority: trimText(testCase?.priority || approvedScenario?.priority || 'Medium', 40),
      adoTestCaseId: trimText(
        testCase?.adoTestCaseId ||
          testCase?.testCaseId ||
          testCase?.workItemId ||
          testCase?.id ||
          '',
        80
      ),
      automationStatus: testCase?.automationStatus || 'Manual',
      steps: Array.isArray(approvedScenario?.steps)
        ? approvedScenario.steps.map((step: any, stepIndex: number) => ({
            order: stepIndex + 1,
            action: trimText(
              typeof step === 'string'
                ? step
                : step?.action || step?.step || step?.description || '',
              220
            ),
            expectedResult: trimText(
              typeof step === 'string'
                ? ''
                : step?.expectedResult ||
                    step?.expected_result ||
                    step?.expected ||
                    '',
              220
            ),
          }))
        : [],
    }
  })
  const riskPlan = input.riskBasedPlan
  const compactRiskPlan = {
    planningStatus: riskPlan?.planningStatus || '',
    releaseRecommendation: trimText(riskPlan?.releaseRecommendation, 250),
    total: riskPlan?.coverageSummary?.total || testScenarios.length,
    recommendedExecutionOrder: Array.isArray(riskPlan?.recommendedExecutionOrder)
      ? riskPlan.recommendedExecutionOrder.slice(0, 20).map((item: any, index: number) => ({
          rank: item.rank || index + 1,
          scenarioId: item.scenarioId || '',
          scenarioTitle: trimText(item.scenarioTitle || item.title, 120),
          testType: item.testType || '',
          priority: item.priority || '',
          executionType: item.executionType || '',
        }))
      : [],
  }

  return {
    operation: 'SYNC_TO_UIPATH_TEST_MANAGER',
    requirementId: String(input.requirementId || 'latest'),
    requirementTitle: trimText(input.requirementTitle || '', 160),
    testManagerProjectKey: input.testManagerProjectKey,
    syncMode: 'RealSync',
    testSetMode: input.testSetMode || 'CreateOrReuseTestSet',
    testScenarios,
    riskPlan: compactRiskPlan,
    source: 'QualityOps UI',
  }
}

function buildFallbackTestManagerPayload(
  requirementId: string,
  testScenarios: Array<Record<string, unknown>>,
  testManagerProjectKey: string
) {
  return {
    operation: 'SYNC_TO_UIPATH_TEST_MANAGER',
    requirementId: String(requirementId || 'latest'),
    testManagerProjectKey,
    syncMode: 'RealSync',
    testSetMode: 'CreateOrReuseTestSet',
    testScenarios: testScenarios.map((testScenario) => ({
      scenarioId: testScenario.scenarioId,
      scenarioTitle: testScenario.scenarioTitle,
      testType: testScenario.testType,
      priority: testScenario.priority,
      adoTestCaseId: testScenario.adoTestCaseId,
      automationStatus: testScenario.automationStatus,
      steps: testScenario.steps,
    })),
    source: 'QualityOps UI',
  }
}

export type AutomationLinkInput = {
  projectId: string
  createdTestCaseIds: string[]
  packageIdentifier: string
  automationMappings?: Array<{
    testCaseId?: string | number
    scenarioId?: string
    packageIdentifier?: string
    entryPoint?: string
    simulatorProfile?: string
  }>
}

export type AutomationLinkMapping = {
  testCaseId?: string | number
  testManagerTestCaseId?: string | number
  scenarioId?: string
  entryPoint?: string
  simulatorProfile?: string
  packageIdentifier?: string
  automatedTestCase?: string
  automatedTestCaseName?: string
  automationTestCase?: string
  status?: string
  blockedReason?: string
}

export type AutomationLinkOutput = {
  automationLinkStatus?: string
  linkedCount?: number
  failedCount?: number
  packageIdentifier?: string
  responseStatusCode?: number | string
  allTestCaseIds?: Array<string | number>
  mappedTestCaseIds?: Array<string | number>
  linkedMappings?: AutomationLinkMapping[]
  blockedReasons?: string[]
  nextAction?: string
}

export type AutomationLinkRunResult = {
  processingStatus: string
  jobId?: number
  jobKey?: string
  jobState?: string
  output?: AutomationLinkOutput
  raw?: unknown
}

export type TestResultTriageMode = 'listExecutions' | 'analyzeExecution' | 'createDefect'

export type TestResultTriageInput = {
  mode: TestResultTriageMode
  projectId: string
  adoParentId?: string
  testExecutionId?: string
  testCaseId?: string
  testCaseName?: string
  variationId?: string
  linkToTestCaseLog?: string
  classification?: string
  evidence?: string
  recommendedAction?: string
}

export type TestManagerExecution = {
  id?: string
  name?: string
  testExecutionId?: string
  testSetId?: string
  executionName?: string
  status?: string
  runId?: string | number
  executionType?: string
  runtimeType?: string
  startedDate?: string
  completedDate?: string
}

export type TestResultExecutionSummary = {
  testExecutionId?: string
  executionName?: string
  status?: string
  testManagerStatus?: string
  executionType?: string
  runtimeType?: string
  totalTests?: number
  passed?: number
  failed?: number
  skipped?: number
}

export type TriageResult = {
  testCaseId?: string
  testCaseName?: string
  resultStatus?: string
  classification?: string
  evidence?: string
  matchedTerms?: string[] | string
  recommendedAction?: string
  robotName?: string
  hostMachine?: string
  automationTestCaseName?: string
  linkToTestCaseLog?: string
  variationId?: string
}

export type TestResultTriageOutput = {
  status?: string
  result?: {
    data?: TestManagerExecution[]
    executions?: TestManagerExecution[]
    paging?: {
      total?: number
    }
    status?: string
    executionSummary?: TestResultExecutionSummary
    triageResults?: TriageResult[]
    overallRecommendation?: string
    executionSummaryUrlUsed?: string
    testCaseLogsUrlUsed?: string
    totalResultRows?: number
    failedResultRows?: number
    robotLogsFetchedCount?: number
    assertionsFetchedCount?: number
    responseStatusCode?: number | string
    message?: string
    blockedReasons?: string[]
  }
  data?: TestManagerExecution[]
  executions?: TestManagerExecution[]
  executionSummary?: TestResultExecutionSummary
  triageResults?: TriageResult[]
  overallRecommendation?: string
  executionSummaryUrlUsed?: string
  testCaseLogsUrlUsed?: string
  totalResultRows?: number
  failedResultRows?: number
  robotLogsFetchedCount?: number
  assertionsFetchedCount?: number
  responseStatusCode?: number | string
  defectCreationStatus?: string
  defectSyncStatus?: string
  defectId?: string
  defectName?: string
  defectSystem?: string
  adoBugId?: string
  adoParentId?: string
  adoBugUrl?: string
  classification?: string
  description?: string
  created?: string
  nextAction?: string
  message?: string
  blockedReasons?: string[]
}

export type TestResultTriageRunResult = {
  processingStatus: string
  jobId?: number
  jobKey?: string
  jobState?: string
  output?: TestResultTriageOutput
  raw?: unknown
}

export type FinalReportMailInput = {
  mode: 'sendFinalReportEmail'
  to: string
  cc: string
  subject: string
  htmlReport: string
  plainTextReport: string
  executionName: string
  adoBugLinks: string[]
  testManagerExecutionLink: string
}

export type FinalReportMailOutput = {
  status?: string
  mailStatus?: string
  emailStatus?: string
  message?: string
  errorMessage?: string
  blockedReasons?: string[]
}

export type FinalReportMailRunResult = {
  processingStatus: string
  jobId?: number
  jobKey?: string
  jobState?: string
  output?: FinalReportMailOutput
  raw?: unknown
}

export type ReviewMemoryScenario = {
  scenarioKey?: string
  title?: string
  reviewStatus?: string
  reviewComment?: string
  reviewedBy?: string
  reviewedAt?: string
  scenarioJson?: string
  stepsJson?: string
  source?: string
  [key: string]: unknown
}

export type ReviewMemoryOutput = {
  status?: string
  message?: string
  scenarios?: ReviewMemoryScenario[]
  records?: ReviewMemoryScenario[]
  reviewMemory?: {
    scenarios?: ReviewMemoryScenario[]
  }
  [key: string]: unknown
}

const ORCHESTRATOR_URL =
  import.meta.env.VITE_UIPATH_ORCHESTRATOR_URL || '/orchestrator-api'

const REQUIREMENT_FOLDER_NAME =
  import.meta.env.VITE_UIPATH_REQUIREMENT_FOLDER_NAME ||
  import.meta.env.VITE_UIPATH_FOLDER_NAME

const REQUIREMENT_AGENT_NAME =
  import.meta.env.VITE_UIPATH_REQUIREMENT_PROCESS_NAME ||
  import.meta.env.VITE_UIPATH_REQUIREMENT_AGENT_NAME

const WRITEBACK_FOLDER_NAME =
  import.meta.env.VITE_UIPATH_ADO_WRITEBACK_FOLDER_NAME

const WRITEBACK_AGENT_NAME =
  import.meta.env.VITE_UIPATH_ADO_WRITEBACK_PROCESS_NAME ||
  import.meta.env.VITE_UIPATH_WRITEBACK_AGENT_NAME

const TEST_SCENARIO_FOLDER_NAME =
  import.meta.env.VITE_UIPATH_TEST_SCENARIO_FOLDER_NAME

const TEST_SCENARIO_AGENT_NAME =
  import.meta.env.VITE_UIPATH_TEST_SCENARIO_PROCESS_NAME

const TESTCASE_WRITEBACK_FOLDER_NAME =
  import.meta.env.VITE_UIPATH_TESTCASE_WRITEBACK_FOLDER_NAME

const TESTCASE_WRITEBACK_AGENT_NAME =
  import.meta.env.VITE_UIPATH_TESTCASE_WRITEBACK_PROCESS_NAME

const TESTCASE_REVIEW_MEMORY_FOLDER_NAME =
  import.meta.env.VITE_UIPATH_TESTCASE_REVIEW_MEMORY_FOLDER_NAME ||
  TESTCASE_WRITEBACK_FOLDER_NAME ||
  'QualityOpsAgent'

const TESTCASE_REVIEW_MEMORY_AGENT_NAME =
  import.meta.env.VITE_UIPATH_TESTCASE_REVIEW_MEMORY_PROCESS_NAME ||
  'QualityOps TestCase Review Memory Agent'

const RISK_PLANNER_FOLDER_NAME =
  import.meta.env.VITE_UIPATH_RISK_PLANNER_FOLDER_NAME

const RISK_PLANNER_AGENT_NAME =
  import.meta.env.VITE_UIPATH_RISK_PLANNER_PROCESS_NAME

const EXECUTION_READINESS_FOLDER_NAME =
  import.meta.env.VITE_UIPATH_EXECUTION_READINESS_FOLDER_NAME

const EXECUTION_READINESS_AGENT_NAME =
  import.meta.env.VITE_UIPATH_EXECUTION_READINESS_PROCESS_NAME

const TEST_MANAGER_WRITEBACK_FOLDER_NAME =
  import.meta.env.VITE_UIPATH_TEST_MANAGER_WRITEBACK_FOLDER_NAME

const TEST_MANAGER_WRITEBACK_AGENT_NAME =
  import.meta.env.VITE_UIPATH_TEST_MANAGER_WRITEBACK_PROCESS_NAME

const AUTOMATION_LINK_FOLDER_NAME =
  import.meta.env.VITE_UIPATH_AUTOMATION_LINK_FOLDER_NAME

const AUTOMATION_LINK_AGENT_NAME =
  import.meta.env.VITE_UIPATH_AUTOMATION_LINK_PROCESS_NAME

const TEST_RESULT_TRIAGE_FOLDER_NAME =
  import.meta.env.VITE_UIPATH_TEST_RESULT_TRIAGE_FOLDER_NAME

const TEST_RESULT_TRIAGE_AGENT_NAME =
  import.meta.env.VITE_UIPATH_TEST_RESULT_TRIAGE_PROCESS_NAME

const FINAL_REPORT_MAIL_FOLDER_NAME =
  import.meta.env.VITE_UIPATH_FINAL_REPORT_MAIL_FOLDER_NAME

const FINAL_REPORT_MAIL_AGENT_NAME =
  import.meta.env.VITE_UIPATH_FINAL_REPORT_MAIL_PROCESS_NAME

function requireConfigValue(value: string | undefined, name: string): string {
  if (!value || !value.trim()) {
    throw new Error(`Missing configuration value: ${name}. Please check your .env file.`)
  }

  return value.trim()
}

async function getAccessToken(uipathSDK: any): Promise<string> {
  if (typeof uipathSDK.getAccessToken === 'function') {
    return await uipathSDK.getAccessToken()
  }

  if (uipathSDK.auth && typeof uipathSDK.auth.getAccessToken === 'function') {
    return await uipathSDK.auth.getAccessToken()
  }

  if (typeof uipathSDK.getToken === 'function') {
    return await uipathSDK.getToken()
  }

  throw new Error('Unable to read UiPath access token from SDK instance.')
}

async function orchestratorFetch(
  uipathSDK: any,
  path: string,
  options: RequestInit = {},
  folderId?: number
) {
  const token = await getAccessToken(uipathSDK)

  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    Accept: 'application/json',
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }

  if (folderId !== undefined && folderId !== null) {
    headers['X-UIPATH-OrganizationUnitId'] = String(folderId)
  }

  const url = `${ORCHESTRATOR_URL}${path}`
  console.log('Calling Orchestrator URL:', url)

  const response = await fetch(url, {
    ...options,
    headers,
  })

  const text = await response.text()

  let data: any = null

  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = text
  }

  if (!response.ok) {
    console.error('StartJobs failed', {
      status: response.status,
      statusText: response.statusText,
      responseBody: text,
      requestBody: options.body,
    })

    throw new Error(
      data?.message ||
        data?.Message ||
        data?.error?.message ||
        data?.error?.Message ||
        `StartJobs failed: ${response.status} ${response.statusText} - ${text}`
    )
  }

  return data
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function encodeODataValue(value: string): string {
  return value.replace(/'/g, "''")
}

function parseRequirementOutputArguments(jobData: any): RequirementAgentOutput | undefined {
  const outputArguments =
    jobData?.OutputArguments ||
    jobData?.outputArguments ||
    jobData?.Info?.OutputArguments ||
    jobData?.Robot?.OutputArguments

  if (!outputArguments) {
    return undefined
  }

  try {
    if (typeof outputArguments === 'string') {
      return JSON.parse(outputArguments)
    }

    return outputArguments
  } catch {
    return {
      processingStatus: String(outputArguments),
    }
  }
}

function parseWriteBackOutputArguments(jobData: any): AdoWriteBackOutput | undefined {
  const outputArguments =
    jobData?.OutputArguments ||
    jobData?.outputArguments ||
    jobData?.Info?.OutputArguments ||
    jobData?.Robot?.OutputArguments

  if (!outputArguments) {
    return undefined
  }

  try {
    if (typeof outputArguments === 'string') {
      return JSON.parse(outputArguments)
    }

    return outputArguments
  } catch {
    return {
      writeBackStatus: String(outputArguments),
    }
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function getNestedValue(source: unknown, ...keys: string[]): unknown {
  let value = source

  for (const key of keys) {
    if (!isRecord(value)) {
      return undefined
    }

    value = value[key]
  }

  return value
}

function hasTestScenarios(value: unknown): boolean {
  return Array.isArray(getNestedValue(value, 'testScenarios'))
}

function selectTestGenerationOutput(value: unknown): unknown {
  const outputValue = getNestedValue(value, 'output')
  const resultValue = getNestedValue(value, 'result')
  const valueValue = getNestedValue(value, 'value')
  const outputArgumentsValue = getNestedValue(value, 'OutputArguments')
  const lowerOutputArgumentsValue = getNestedValue(value, 'outputArguments')

  if (hasTestScenarios(value)) {
    return value
  }

  if (hasTestScenarios(outputValue)) {
    return outputValue
  }

  if (hasTestScenarios(resultValue)) {
    return resultValue
  }

  if (hasTestScenarios(outputArgumentsValue)) {
    return outputArgumentsValue
  }

  const outputArgumentsOutput = getNestedValue(outputArgumentsValue, 'output')
  if (outputArgumentsOutput !== undefined) {
    return outputArgumentsOutput
  }

  const outputArgumentsResult = getNestedValue(outputArgumentsValue, 'result')
  if (outputArgumentsResult !== undefined) {
    return outputArgumentsResult
  }

  if (hasTestScenarios(lowerOutputArgumentsValue)) {
    return lowerOutputArgumentsValue
  }

  const lowerOutputArgumentsOutput = getNestedValue(lowerOutputArgumentsValue, 'output')
  if (lowerOutputArgumentsOutput !== undefined) {
    return lowerOutputArgumentsOutput
  }

  const lowerOutputArgumentsResult = getNestedValue(lowerOutputArgumentsValue, 'result')
  if (lowerOutputArgumentsResult !== undefined) {
    return lowerOutputArgumentsResult
  }

  return (
    getNestedValue(value, 'Info', 'OutputArguments') ??
    getNestedValue(value, 'Robot', 'OutputArguments') ??
    outputValue ??
    resultValue ??
    valueValue ??
    getNestedValue(value, 'raw') ??
    value
  )
}

export function parseTestGenerationAgentOutput(raw: unknown): TestScenarioGenerationOutput | null {
  let output = raw

  for (let attempt = 0; attempt < 4; attempt += 1) {
    const currentOutput = output
    const nextOutput = selectTestGenerationOutput(output)

    output = nextOutput

    if (typeof output === 'string') {
      try {
        output = JSON.parse(output) as unknown
      } catch {
        console.error('Test Generation output is string but not valid JSON', output)
        return null
      }

      continue
    }

    if (nextOutput === currentOutput) {
      break
    }
  }

  const questionValue = getNestedValue(output, 'question')

  if (typeof questionValue === 'string') {
    try {
      const nested = JSON.parse(questionValue) as unknown
      if (hasTestScenarios(nested)) {
        output = nested
      }
    } catch {
      // ignore
    }
  }

  const valueString = getNestedValue(output, 'value')

  if (typeof valueString === 'string') {
    try {
      const nested = JSON.parse(valueString) as unknown
      if (hasTestScenarios(nested)) {
        output = nested
      }
    } catch {
      // ignore
    }
  }

  if (
  isRecord(output) &&
  (
    Array.isArray(output.testScenarios) ||
    typeof output.generationStatus === 'string' ||
    typeof output.generationMode === 'string'
  )
) {
  return output as TestScenarioGenerationOutput
}

return null
}

function parseTestScenarioGenerationOutputArguments(
  jobData: any
): TestScenarioGenerationOutput | undefined {
  const outputArguments =
    jobData?.OutputArguments ||
    jobData?.outputArguments ||
    jobData?.Info?.OutputArguments ||
    jobData?.Robot?.OutputArguments

  if (!outputArguments) {
    console.warn('No Test Scenario OutputArguments found on jobData', jobData)
    return undefined
  }

  let parsed: unknown = outputArguments

  try {
    if (typeof parsed === 'string') {
      parsed = JSON.parse(parsed)
    }

    const parsedOutput = parseTestGenerationAgentOutput(parsed)

    if (parsedOutput) {
      return parsedOutput
    }

    if (isRecord(parsed) && typeof parsed.question === 'string') {
      const nested = JSON.parse(parsed.question)
      return parseTestGenerationAgentOutput(nested) ?? undefined
    }

    return undefined
  } catch (error) {
    console.error('Failed to parse Test Scenario OutputArguments', error, outputArguments)
    return {
      generationStatus: String(outputArguments),
    }
  }
}

function parseAdoTestCaseWriteBackOutputArguments(
  jobData: any
): AdoTestCaseWriteBackOutput | undefined {
  const outputArguments =
    jobData?.OutputArguments ||
    jobData?.outputArguments ||
    jobData?.Info?.OutputArguments ||
    jobData?.Robot?.OutputArguments

  if (!outputArguments) {
    return undefined
  }

  try {
    if (typeof outputArguments === 'string') {
      return JSON.parse(outputArguments)
    }

    return outputArguments
  } catch {
    return {
      writeBackStatus: String(outputArguments),
    }
  }
}

function parseRiskBasedTestPlannerOutputArguments(
  jobData: any
): RiskBasedTestPlannerOutput | undefined {
  const outputArguments =
    jobData?.OutputArguments ||
    jobData?.outputArguments ||
    jobData?.Info?.OutputArguments ||
    jobData?.Robot?.OutputArguments

  if (!outputArguments) {
    return undefined
  }

  try {
    if (typeof outputArguments === 'string') {
      return JSON.parse(outputArguments)
    }

    return outputArguments
  } catch {
    return {
      planningStatus: String(outputArguments),
    }
  }
}

function parseExecutionReadinessOutputArguments(
  jobData: any
): ExecutionReadinessOutput | undefined {
  const outputArguments =
    jobData?.OutputArguments ||
    jobData?.outputArguments ||
    jobData?.Info?.OutputArguments ||
    jobData?.Robot?.OutputArguments

  if (!outputArguments) {
    return undefined
  }

  try {
    if (typeof outputArguments === 'string') {
      return JSON.parse(outputArguments)
    }

    return outputArguments
  } catch {
    return {
      readinessStatus: String(outputArguments),
    }
  }
}

function parseTestManagerWriteBackOutputArguments(
  jobData: any
): TestManagerWriteBackOutput | undefined {
  const outputArguments =
    jobData?.OutputArguments ||
    jobData?.outputArguments ||
    jobData?.Info?.OutputArguments ||
    jobData?.Robot?.OutputArguments

  if (!outputArguments) {
    return undefined
  }

  try {
    if (typeof outputArguments === 'string') {
      return JSON.parse(outputArguments)
    }

    return outputArguments
  } catch {
    return {
      syncStatus: String(outputArguments),
    }
  }
}

function parseAutomationLinkOutputArguments(
  jobData: any
): AutomationLinkOutput | undefined {
  const outputArguments =
    jobData?.OutputArguments ||
    jobData?.outputArguments ||
    jobData?.Info?.OutputArguments ||
    jobData?.Robot?.OutputArguments

  if (!outputArguments) {
    return undefined
  }

  try {
    if (typeof outputArguments === 'string') {
      return JSON.parse(outputArguments)
    }

    return outputArguments
  } catch {
    return {
      automationLinkStatus: String(outputArguments),
    }
  }
}

function parseTestResultTriageOutputArguments(
  jobData: any
): TestResultTriageOutput | undefined {
  const outputArguments =
    jobData?.OutputArguments ||
    jobData?.outputArguments ||
    jobData?.Info?.OutputArguments ||
    jobData?.Robot?.OutputArguments

  if (!outputArguments) {
    return undefined
  }

  try {
    if (typeof outputArguments === 'string') {
      return JSON.parse(outputArguments)
    }

    return outputArguments
  } catch {
    return {
      status: String(outputArguments),
    }
  }
}

function parseFinalReportMailOutputArguments(
  jobData: any
): FinalReportMailOutput | undefined {
  const outputArguments =
    jobData?.OutputArguments ||
    jobData?.outputArguments ||
    jobData?.Info?.OutputArguments ||
    jobData?.Robot?.OutputArguments

  if (!outputArguments) {
    return undefined
  }

  try {
    if (typeof outputArguments === 'string') {
      return JSON.parse(outputArguments)
    }

    return outputArguments
  } catch {
    return {
      status: String(outputArguments),
    }
  }
}

export async function getFolderIdByName(
  uipathSDK: any,
  folderName: string
): Promise<number> {
  const validFolderName = requireConfigValue(folderName, 'folderName')
  const encodedName = encodeODataValue(validFolderName)

  const data = await orchestratorFetch(
    uipathSDK,
    `/odata/Folders?$filter=DisplayName eq '${encodedName}'`
  )

  const folder = data?.value?.[0]

  if (!folder?.Id) {
    throw new Error(`Folder not found: ${validFolderName}`)
  }

  return folder.Id
}

export async function getReleaseKeyByName(
  uipathSDK: any,
  folderId: number,
  releaseName: string
): Promise<string> {
  const validReleaseName = requireConfigValue(releaseName, 'releaseName')
  const encodedName = encodeODataValue(validReleaseName)

  const data = await orchestratorFetch(
    uipathSDK,
    `/odata/Releases?$filter=Name eq '${encodedName}'`,
    {},
    folderId
  )

  const release = data?.value?.[0]

  if (!release?.Key) {
    throw new Error(`Published agent/process not found: ${validReleaseName}`)
  }

  return release.Key
}

async function getJobStatus(uipathSDK: any, folderId: number, jobId: number) {
  return await orchestratorFetch(
    uipathSDK,
    `/odata/Jobs(${jobId})?$select=Id,Key,State,OutputArguments,Info,StartTime,EndTime,ReleaseName`,
    {},
    folderId
  )
}

export async function runRequirementAgent(
  uipathSDK: any,
  input: RequirementAgentInput,
  onStatus?: (message: string) => void
): Promise<RequirementAgentRunResult> {
  const requirementFolderName = requireConfigValue(
    REQUIREMENT_FOLDER_NAME,
    'VITE_UIPATH_REQUIREMENT_FOLDER_NAME or VITE_UIPATH_FOLDER_NAME'
  )

  const requirementAgentName = requireConfigValue(
    REQUIREMENT_AGENT_NAME,
    'VITE_UIPATH_REQUIREMENT_PROCESS_NAME or VITE_UIPATH_REQUIREMENT_AGENT_NAME'
  )

  onStatus?.(`Getting UiPath folder: ${requirementFolderName}`)
  const folderId = await getFolderIdByName(uipathSDK, requirementFolderName)

  onStatus?.(`Getting published requirement coded agent: ${requirementAgentName}`)
  const releaseKey = await getReleaseKeyByName(uipathSDK, folderId, requirementAgentName)

  onStatus?.('Starting requirement analysis job...')

  const body = {
    startInfo: {
      ReleaseKey: releaseKey,
      Strategy: 'ModernJobsCount',
      JobsCount: 1,
      InputArguments: JSON.stringify({
        requirementId: input.requirementId,
        submittedBy: input.submittedBy,
        environment: input.environment,
      }),
    },
  }

  const startData = await orchestratorFetch(
    uipathSDK,
    `/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    },
    folderId
  )

  const job = startData?.value?.[0] || startData?.Value?.[0] || startData?.[0]

  if (!job?.Id) {
    return {
      processingStatus: 'Requirement analysis job started, but job ID was not returned.',
      raw: startData,
    }
  }

  onStatus?.(`Requirement analysis job started. Job ID: ${job.Id}`)

  let latestJob = job

  for (let attempt = 1; attempt <= 30; attempt += 1) {
    await sleep(2000)

    latestJob = await getJobStatus(uipathSDK, folderId, job.Id)
    const state = latestJob?.State || latestJob?.state || 'Unknown'

    onStatus?.(`Waiting for requirement analysis result... Current state: ${state}`)

    if (state === 'Successful') {
      const output = parseRequirementOutputArguments(latestJob)

      return {
        processingStatus: output?.processingStatus || 'Requirement analysis completed successfully.',
        jobId: job.Id,
        jobKey: job.Key,
        jobState: state,
        output,
        raw: latestJob,
      }
    }

    if (['Faulted', 'Stopped', 'Suspended'].includes(state)) {
      throw new Error(`Requirement analysis job ended with state: ${state}`)
    }
  }

  return {
    processingStatus: 'Requirement analysis job started but output was not available yet.',
    jobId: job.Id,
    jobKey: job.Key,
    jobState: latestJob?.State || 'Unknown',
    raw: latestJob,
  }
}

export async function runAdoWriteBackAgent(
  uipathSDK: any,
  input: AdoWriteBackInput,
  onStatus?: (message: string) => void
): Promise<AdoWriteBackRunResult> {
  const writeBackFolderName = requireConfigValue(
    WRITEBACK_FOLDER_NAME,
    'VITE_UIPATH_ADO_WRITEBACK_FOLDER_NAME'
  )

  const writeBackAgentName = requireConfigValue(
    WRITEBACK_AGENT_NAME,
    'VITE_UIPATH_ADO_WRITEBACK_PROCESS_NAME or VITE_UIPATH_WRITEBACK_AGENT_NAME'
  )

  onStatus?.(`Getting UiPath folder: ${writeBackFolderName}`)
  const folderId = await getFolderIdByName(uipathSDK, writeBackFolderName)

  onStatus?.(`Getting published ADO WriteBack agent: ${writeBackAgentName}`)
  const releaseKey = await getReleaseKeyByName(uipathSDK, folderId, writeBackAgentName)

  onStatus?.('Starting ADO WriteBack job...')

  const questionPayload = {
    mode: input.mode,
    requirementId: input.requirementId,
    commentTitle: input.commentTitle,
    qaLeadReview: input.qaLeadReview,
    commentHtml: input.commentHtml,
    decisionType: input.decisionType,
    decisionComment: input.decisionComment,
    submittedBy: input.submittedBy,
    environment: input.environment,
  }

  const body = {
    startInfo: {
      ReleaseKey: releaseKey,
      Strategy: 'ModernJobsCount',
      JobsCount: 1,
      InputArguments: JSON.stringify({
        question: JSON.stringify(questionPayload),
      }),
    },
  }

  const startData = await orchestratorFetch(
    uipathSDK,
    `/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    },
    folderId
  )

  const job = startData?.value?.[0] || startData?.Value?.[0] || startData?.[0]

  if (!job?.Id) {
    return {
      processingStatus: 'ADO WriteBack job started, but job ID was not returned.',
      raw: startData,
    }
  }

  onStatus?.(`ADO WriteBack job started. Job ID: ${job.Id}`)

  let latestJob = job

  for (let attempt = 1; attempt <= 30; attempt += 1) {
    await sleep(2000)

    latestJob = await getJobStatus(uipathSDK, folderId, job.Id)
    const state = latestJob?.State || latestJob?.state || 'Unknown'

    onStatus?.(`Waiting for ADO write-back result... Current state: ${state}`)

    if (state === 'Successful') {
      const output = parseWriteBackOutputArguments(latestJob)
      const outputStatus = output?.status || output?.writeBackStatus
      const errorMessage = output?.errorMessage || output?.blockedReasons?.join(' ')

      if (errorMessage || outputStatus?.toLowerCase() === 'failed') {
        throw new Error(errorMessage || 'Azure DevOps writeback returned a failed status.')
      }

      return {
        processingStatus: output?.writeBackStatus || output?.message || 'ADO WriteBack completed successfully.',
        jobId: job.Id,
        jobKey: job.Key,
        jobState: state,
        output,
        raw: latestJob,
      }
    }

    if (['Faulted', 'Stopped', 'Suspended'].includes(state)) {
      throw new Error(`ADO WriteBack job ended with state: ${state}`)
    }
  }

  return {
    processingStatus: 'ADO WriteBack job started but output was not available yet.',
    jobId: job.Id,
    jobKey: job.Key,
    jobState: latestJob?.State || 'Unknown',
    raw: latestJob,
  }
}

export async function runTestScenarioGenerationAgent(
  uipathSDK: any,
  input: TestScenarioGenerationInput,
  onStatus?: (message: string) => void
): Promise<TestScenarioGenerationRunResult> {
  const testScenarioFolderName = requireConfigValue(
    TEST_SCENARIO_FOLDER_NAME,
    'VITE_UIPATH_TEST_SCENARIO_FOLDER_NAME'
  )

  const testScenarioAgentName = requireConfigValue(
    TEST_SCENARIO_AGENT_NAME,
    'VITE_UIPATH_TEST_SCENARIO_PROCESS_NAME'
  )

  onStatus?.(`Getting UiPath folder: ${testScenarioFolderName}`)
  const folderId = await getFolderIdByName(uipathSDK, testScenarioFolderName)

  onStatus?.(`Getting published Test Scenario Generation agent: ${testScenarioAgentName}`)
  const releaseKey = await getReleaseKeyByName(uipathSDK, folderId, testScenarioAgentName)

  onStatus?.('Starting Test Scenario Generation job...')

  const questionPayload = {
    requirementId: input.requirementId,
    submittedBy: input.submittedBy,
    environment: input.environment,
    requirementAnalysis: input.requirementAnalysis,
    qaLeadReview: input.qaLeadReview,
    requirementTitle: input.requirementTitle,
    requirementDescription: input.requirementDescription,
    acceptanceCriteria: input.acceptanceCriteria,
    riskLevel: input.riskLevel,
    testingScope: input.testingScope,
    suggestedTestFocus: input.suggestedTestFocus,
  }

  const body = {
    startInfo: {
      ReleaseKey: releaseKey,
      Strategy: 'ModernJobsCount',
      JobsCount: 1,
      InputArguments: JSON.stringify({
        question: JSON.stringify(questionPayload),
      }),
    },
  }

  const startData = await orchestratorFetch(
    uipathSDK,
    `/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    },
    folderId
  )

  const job = startData?.value?.[0] || startData?.Value?.[0] || startData?.[0]

  if (!job?.Id) {
    return {
      processingStatus: 'Test Scenario Generation job started, but job ID was not returned.',
      raw: startData,
    }
  }

  onStatus?.(`Test Scenario Generation job started. Job ID: ${job.Id}`)

  let latestJob = job

  for (let attempt = 1; attempt <= 90; attempt += 1) {
    await sleep(3000)

    latestJob = await getJobStatus(uipathSDK, folderId, job.Id)
    const state = latestJob?.State || latestJob?.state || 'Unknown'

    onStatus?.(`Waiting for test scenario generation result... Current state: ${state}`)

    if (state === 'Successful') {
      const output = parseTestScenarioGenerationOutputArguments(latestJob)

      return {
        processingStatus:
          output?.generationStatus || 'Test Scenario Generation completed successfully.',
        jobId: job.Id,
        jobKey: job.Key,
        jobState: state,
        output,
        raw: latestJob,
      }
    }

    if (['Faulted', 'Stopped', 'Suspended'].includes(state)) {
      throw new Error(`Test Scenario Generation job ended with state: ${state}`)
    }
  }

  return {
    processingStatus:
      'Test Scenario Generation is still running. Please wait and try again after some time.',
    jobId: job.Id,
    jobKey: job.Key,
    jobState: latestJob?.State || 'Unknown',
  raw: latestJob,
  }
}

const normalizeTestStep = (step: any): TestCaseStep => {
  if (typeof step === 'string') {
    return {
      action: step,
      expectedResult: '',
    }
  }

  return {
    action: step?.action || step?.description || step?.step || '',
    expectedResult: step?.expectedResult || step?.expected || step?.result || '',
  }
}

const normalizeTestCase = (scenario: any, index: number): TestScenario => {
  const steps = Array.isArray(scenario.steps) ? scenario.steps.map(normalizeTestStep) : []
  const title =
    scenario.title ||
    scenario.name ||
    scenario.scenarioTitle ||
    `AI Generated Test Case ${index + 1}`

  return {
    scenarioKey: scenario.scenarioKey,
    scenarioId: scenario.scenarioId,
    title,
    scenarioTitle: scenario.scenarioTitle || title,
    description:
      scenario.description ||
      scenario.summary ||
      'Generated by QualityOps AI Test Generation Agent',
    priority: scenario.priority || '2',
    steps,
    reviewStatus: scenario.reviewStatus,
    reviewComment: scenario.reviewComment,
    reviewedBy: scenario.reviewedBy,
    reviewedAt: scenario.reviewedAt,
  }
}

export async function runAdoTestCaseWriteBackAgent(
  uipathSDK: any,
  input: AdoTestCaseWriteBackInput,
  onStatus?: (message: string) => void
): Promise<AdoTestCaseWriteBackRunResult> {
  const testCaseWriteBackFolderName = requireConfigValue(
    TESTCASE_WRITEBACK_FOLDER_NAME,
    'VITE_UIPATH_TESTCASE_WRITEBACK_FOLDER_NAME'
  )

  const testCaseWriteBackAgentName = requireConfigValue(
    TESTCASE_WRITEBACK_AGENT_NAME,
    'VITE_UIPATH_TESTCASE_WRITEBACK_PROCESS_NAME'
  )

  onStatus?.(`Getting UiPath folder: ${testCaseWriteBackFolderName}`)
  const folderId = await getFolderIdByName(uipathSDK, testCaseWriteBackFolderName)

  onStatus?.(`Getting published Azure DevOps Test Case WriteBack agent: ${testCaseWriteBackAgentName}`)
  const releaseKey = await getReleaseKeyByName(
    uipathSDK,
    folderId,
    testCaseWriteBackAgentName
  )

  onStatus?.('Starting Azure DevOps Test Case WriteBack job...')

  const normalizedTestScenarios = input.testScenarios.map((scenario, index) =>
    normalizeTestCase(scenario, index)
  )

  if (!Array.isArray(normalizedTestScenarios) || normalizedTestScenarios.length === 0) {
    throw new Error('No generated test scenarios available to create test cases.')
  }

  console.log('ADO Test Case WriteBack normalized scenario count:', normalizedTestScenarios.length)
  console.log('ADO Test Case WriteBack normalized scenarios:', normalizedTestScenarios)

  const questionPayload = {
    testScenarios: normalizedTestScenarios,
    requirementId: String(input.requirementId || ''),
    source: 'QualityOps UI',
    instruction: 'Create Azure DevOps Test Case work items from the generated test scenarios.',
  }

  const inputArguments = {
    question: JSON.stringify(questionPayload),
  }

  const body = {
    startInfo: {
      ReleaseKey: releaseKey,
      Strategy: 'ModernJobsCount',
      JobsCount: 1,
      InputArguments: JSON.stringify(inputArguments),
    },
  }

  console.log('ADO Test Case WriteBack StartJobs input:', inputArguments)
  console.log('ADO Test Case WriteBack StartJobs body:', body)

  const startData = await orchestratorFetch(
    uipathSDK,
    `/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    },
    folderId
  )

  const job = startData?.value?.[0] || startData?.Value?.[0] || startData?.[0]

  if (!job?.Id) {
    return {
      processingStatus: 'Azure DevOps Test Case WriteBack job started, but job ID was not returned.',
      raw: startData,
    }
  }

  onStatus?.(`Azure DevOps Test Case WriteBack job started. Job ID: ${job.Id}`)

  let latestJob = job

  for (let attempt = 1; attempt <= 30; attempt += 1) {
    await sleep(2000)

    latestJob = await getJobStatus(uipathSDK, folderId, job.Id)
    const state = latestJob?.State || latestJob?.state || 'Unknown'

    onStatus?.(`Waiting for ADO test case write-back result... Current state: ${state}`)

    if (state === 'Successful') {
      const output = parseAdoTestCaseWriteBackOutputArguments(latestJob)
      const createdCount = output?.createdTestCases?.length ?? 0
      const failedCount = output?.failedScenarios?.length ?? 0
      const writeBackStatus = output?.writeBackStatus?.toLowerCase() || ''

      if (failedCount || writeBackStatus.includes('fail') || writeBackStatus.includes('error')) {
        console.error('ADO Test Case WriteBack returned failures:', {
          writeBackStatus: output?.writeBackStatus,
          createdBeforeFailure: createdCount,
          failedScenarios: output?.failedScenarios,
          output,
        })
      }

      return {
        processingStatus:
          output?.writeBackStatus ||
          `Azure DevOps Test Case WriteBack completed. Created: ${createdCount}, Failed: ${failedCount}.`,
        jobId: job.Id,
        jobKey: job.Key,
        jobState: state,
        output,
        raw: latestJob,
      }
    }

    if (['Faulted', 'Stopped', 'Suspended'].includes(state)) {
      throw new Error(`Azure DevOps Test Case WriteBack job ended with state: ${state}`)
    }
  }

  return {
    processingStatus: 'Azure DevOps Test Case WriteBack job started but output was not available yet.',
    jobId: job.Id,
    jobKey: job.Key,
    jobState: latestJob?.State || 'Unknown',
    raw: latestJob,
  }
}

export const buildScenarioKey = (
  requirementId: string,
  title: string,
  index: number
): string => {
  const safeTitle = String(title || 'scenario')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
    .slice(0, 80)

  return `${requirementId || 'latest'}-${index}-${safeTitle}`
}

function getReviewScenarioTitle(scenario: any, index: number): string {
  return (
    scenario?.scenarioTitle ||
    scenario?.title ||
    scenario?.name ||
    `Generated Test Scenario ${index + 1}`
  )
}

function normalizeReviewStep(step: any) {
  if (typeof step === 'string') {
    return {
      action: step,
      expectedResult: '',
    }
  }

  return {
    action: step?.action || step?.step || step?.description || '',
    expectedResult:
      step?.expectedResult ||
      step?.expected_result ||
      step?.expected ||
      step?.result ||
      '',
  }
}

function buildCompactReviewMemoryScenario(
  scenario: any,
  index: number,
  requirementId: string
): ReviewMemoryScenario {
  const title = getReviewScenarioTitle(scenario, index).replace(/\s+/g, ' ').trim()
  const scenarioKey =
    scenario?.scenarioKey || buildScenarioKey(String(requirementId || 'latest'), title, index)
  const reviewStatus = scenario?.reviewStatus || 'Pending'

  return {
    scenarioKey,
    title,
    reviewStatus,
    reviewComment: scenario?.reviewComment || '',
    reviewedBy: scenario?.reviewedBy || '',
    reviewedAt: scenario?.reviewedAt || '',
    scenarioJson: JSON.stringify({
      scenarioKey,
      title,
      description: scenario?.description || '',
      priority: scenario?.priority || '',
      reviewStatus,
    }),
    stepsJson: JSON.stringify(
      Array.isArray(scenario?.steps) ? scenario.steps.map(normalizeReviewStep) : []
    ),
    source: 'QualityOps UI',
  }
}

function chunkArray<T>(items: T[], size: number): T[][] {
  const chunks: T[][] = []

  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size))
  }

  return chunks
}

function parseReviewMemoryOutput(jobData: any): ReviewMemoryOutput | undefined {
  const outputArguments =
    jobData?.OutputArguments ||
    jobData?.outputArguments ||
    jobData?.Info?.OutputArguments ||
    jobData?.Robot?.OutputArguments

  if (!outputArguments) {
    return undefined
  }

  try {
    let parsed = typeof outputArguments === 'string' ? JSON.parse(outputArguments) : outputArguments

    if (typeof parsed?.question === 'string') {
      parsed = JSON.parse(parsed.question)
    }

    if (typeof parsed?.output === 'string') {
      parsed = JSON.parse(parsed.output)
    }

    if (typeof parsed?.result === 'string') {
      parsed = JSON.parse(parsed.result)
    }

    return parsed
  } catch {
    return {
      status: String(outputArguments),
    }
  }
}

async function runTestCaseReviewMemoryAgent(
  uipathSDK: any,
  payload: Record<string, unknown>
): Promise<ReviewMemoryOutput | undefined> {
  const folderId = await getFolderIdByName(uipathSDK, TESTCASE_REVIEW_MEMORY_FOLDER_NAME)
  const releaseKey = await getReleaseKeyByName(
    uipathSDK,
    folderId,
    TESTCASE_REVIEW_MEMORY_AGENT_NAME
  )

  const inputArguments = JSON.stringify({
    question: JSON.stringify(payload),
  })

  console.log('Memory Agent InputArguments length:', inputArguments.length)

  if (inputArguments.length >= 10000) {
    console.warn('Memory Agent payload is too large. Compacting required.')
  }

  const requestBody = {
    startInfo: {
      ReleaseKey: releaseKey,
      Strategy: 'ModernJobsCount',
      JobsCount: 1,
      InputArguments: inputArguments,
    },
  }

  console.log('Memory Agent StartJobs request body:', requestBody)
  console.log('Memory Agent InputArguments type:', typeof requestBody.startInfo.InputArguments)

  const startData = await orchestratorFetch(
    uipathSDK,
    `/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs`,
    {
      method: 'POST',
      body: JSON.stringify(requestBody),
    },
    folderId
  )

  const job = startData?.value?.[0] || startData?.Value?.[0] || startData?.[0]

  if (!job?.Id) {
    return {
      status: 'StartedWithoutJobId',
      message: 'TestCase Review Memory job started, but job ID was not returned.',
    }
  }

  let latestJob = job

  for (let attempt = 1; attempt <= 30; attempt += 1) {
    await sleep(2000)

    latestJob = await getJobStatus(uipathSDK, folderId, job.Id)
    const state = latestJob?.State || latestJob?.state || 'Unknown'

    if (state === 'Successful') {
      return parseReviewMemoryOutput(latestJob)
    }

    if (['Faulted', 'Stopped', 'Suspended'].includes(state)) {
      throw new Error(`TestCase Review Memory job ended with state: ${state}`)
    }
  }

  return {
    status: 'Running',
    message: 'TestCase Review Memory job is still running.',
  }
}

export async function saveReviewMemoryToDataService(
  uipathSDK: any,
  requirementId: string,
  scenarios: any[]
): Promise<ReviewMemoryOutput | undefined> {
  const validRequirementId = String(requirementId || 'latest')
  const normalizedScenarios = scenarios.map((scenario, index) =>
    buildCompactReviewMemoryScenario(scenario, index, validRequirementId)
  )

  console.log('Saving review memory count:', normalizedScenarios.length)
  console.log('Review memory scenario keys:', normalizedScenarios.map((scenario) => scenario.scenarioKey))

  let latestOutput: ReviewMemoryOutput | undefined

  for (const scenarioChunk of chunkArray(normalizedScenarios, 2)) {
    const payload = {
      operation: 'SAVE_REVIEW_MEMORY',
      requirementId: validRequirementId,
      scenarios: scenarioChunk,
    }

    latestOutput = await runTestCaseReviewMemoryAgent(uipathSDK, payload)
    const outputText = `${latestOutput?.status || ''} ${latestOutput?.message || ''}`.toLowerCase()

    if (outputText.includes('fail') || outputText.includes('error')) {
      throw new Error(latestOutput?.message || latestOutput?.status || 'SAVE_REVIEW_MEMORY failed.')
    }
  }

  return latestOutput
}

export async function loadReviewMemoryFromDataService(
  uipathSDK: any,
  requirementId: string
): Promise<ReviewMemoryOutput | undefined> {
  return await runTestCaseReviewMemoryAgent(uipathSDK, {
    operation: 'LOAD_REVIEW_MEMORY',
    requirementId: String(requirementId || 'latest'),
  })
}

export async function updateReviewMemoryWithAdoResults(
  uipathSDK: any,
  requirementId: string,
  createdTestCases: unknown[]
): Promise<ReviewMemoryOutput | undefined> {
  return await runTestCaseReviewMemoryAgent(uipathSDK, {
    operation: 'UPDATE_ADO_CREATION_RESULT',
    requirementId: String(requirementId || 'latest'),
    createdTestCases,
  })
}

export async function runRiskBasedTestPlannerAgent(
  uipathSDK: any,
  input: RiskBasedTestPlannerInput,
  onStatus?: (message: string) => void
): Promise<RiskBasedTestPlannerRunResult> {
  const riskPlannerFolderName = requireConfigValue(
    RISK_PLANNER_FOLDER_NAME,
    'VITE_UIPATH_RISK_PLANNER_FOLDER_NAME'
  )

  const riskPlannerAgentName = requireConfigValue(
    RISK_PLANNER_AGENT_NAME,
    'VITE_UIPATH_RISK_PLANNER_PROCESS_NAME'
  )

  onStatus?.(`Getting UiPath folder: ${riskPlannerFolderName}`)
  const folderId = await getFolderIdByName(uipathSDK, riskPlannerFolderName)

  onStatus?.(`Getting published Risk-Based Test Planner agent: ${riskPlannerAgentName}`)
  const releaseKey = await getReleaseKeyByName(uipathSDK, folderId, riskPlannerAgentName)

  onStatus?.('Starting Risk-Based Test Planner job...')

  let questionPayload = buildCompactRiskPlanPayload(input)
  let inputArguments = JSON.stringify({
    question: JSON.stringify(questionPayload),
  })

  if (inputArguments.length > 9500) {
    console.warn('Risk Planner payload too large, trimming approved test cases.')
    questionPayload = {
      ...questionPayload,
      testScenarios: questionPayload.testScenarios.slice(0, 20).map((testCase) => ({
        scenarioId: testCase.scenarioId,
        scenarioTitle: testCase.scenarioTitle,
        testType: testCase.testType,
        priority: testCase.priority,
        riskLevel: testCase.riskLevel,
        adoTestCaseId: testCase.adoTestCaseId,
        reviewStatus: testCase.reviewStatus,
        module: testCase.module,
        description: '',
      })),
    }
    inputArguments = JSON.stringify({
      question: JSON.stringify(questionPayload),
    })
  }

  console.log('Risk Based Planner testScenarios count:', questionPayload.testScenarios.length)
  console.log('Risk Planner testScenarios:', questionPayload.testScenarios)
  console.log('Risk Planner first scenario:', questionPayload.testScenarios[0])
  console.log('Risk Based Planner payload:', questionPayload)
  console.log('Risk Based Planner InputArguments length:', inputArguments.length)

  const body = {
    startInfo: {
      ReleaseKey: releaseKey,
      Strategy: 'ModernJobsCount',
      JobsCount: 1,
      InputArguments: inputArguments,
    },
  }

  const startData = await orchestratorFetch(
    uipathSDK,
    `/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    },
    folderId
  )

  const job = startData?.value?.[0] || startData?.Value?.[0] || startData?.[0]

  if (!job?.Id) {
    return {
      processingStatus: 'Risk-Based Test Planner job started, but job ID was not returned.',
      raw: startData,
    }
  }

  onStatus?.(`Risk-Based Test Planner job started. Job ID: ${job.Id}`)

  let latestJob = job

  for (let attempt = 1; attempt <= 30; attempt += 1) {
    await sleep(2000)

    latestJob = await getJobStatus(uipathSDK, folderId, job.Id)
    const state = latestJob?.State || latestJob?.state || 'Unknown'

    onStatus?.(`Waiting for risk-based execution plan... Current state: ${state}`)

    if (state === 'Successful') {
      const output = parseRiskBasedTestPlannerOutputArguments(latestJob)

      return {
        processingStatus:
          output?.planningStatus || 'Risk-Based Test Planner completed successfully.',
        jobId: job.Id,
        jobKey: job.Key,
        jobState: state,
        output,
        raw: latestJob,
      }
    }

    if (['Faulted', 'Stopped', 'Suspended'].includes(state)) {
      throw new Error(`Risk-Based Test Planner job ended with state: ${state}`)
    }
  }

  return {
    processingStatus: 'Risk-Based Test Planner job started but output was not available yet.',
    jobId: job.Id,
    jobKey: job.Key,
    jobState: latestJob?.State || 'Unknown',
    raw: latestJob,
  }
}

export async function runExecutionReadinessAgent(
  uipathSDK: any,
  input: ExecutionReadinessInput,
  onStatus?: (message: string) => void
): Promise<ExecutionReadinessRunResult> {
  const executionReadinessFolderName = requireConfigValue(
    EXECUTION_READINESS_FOLDER_NAME,
    'VITE_UIPATH_EXECUTION_READINESS_FOLDER_NAME'
  )

  const executionReadinessAgentName = requireConfigValue(
    EXECUTION_READINESS_AGENT_NAME,
    'VITE_UIPATH_EXECUTION_READINESS_PROCESS_NAME'
  )

  onStatus?.(`Getting UiPath folder: ${executionReadinessFolderName}`)
  const folderId = await getFolderIdByName(uipathSDK, executionReadinessFolderName)

  onStatus?.(`Getting published Execution Readiness agent: ${executionReadinessAgentName}`)
  const releaseKey = await getReleaseKeyByName(
    uipathSDK,
    folderId,
    executionReadinessAgentName
  )

  onStatus?.('Starting Test Cloud Execution Readiness job...')

  const questionPayload = {
    requirementId: input.requirementId,
    submittedBy: input.submittedBy,
    environment: input.environment,
    requirementTitle: input.requirementTitle,
    riskLevel: input.riskLevel,
    qaReviewStatus: input.qaReviewStatus,
    testScenarioCount: input.testScenarioCount,
    adoTestCaseCreatedCount: input.adoTestCaseCreatedCount,
    riskPlanningStatus: input.riskPlanningStatus,
    recommendedExecutionOrder: input.recommendedExecutionOrder,
    coverageSummary: input.coverageSummary,
  }

  const body = {
    startInfo: {
      ReleaseKey: releaseKey,
      Strategy: 'ModernJobsCount',
      JobsCount: 1,
      InputArguments: JSON.stringify({
        question: JSON.stringify(questionPayload),
      }),
    },
  }

  const startData = await orchestratorFetch(
    uipathSDK,
    `/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    },
    folderId
  )

  const job = startData?.value?.[0] || startData?.Value?.[0] || startData?.[0]

  if (!job?.Id) {
    return {
      processingStatus: 'Execution Readiness job started, but job ID was not returned.',
      raw: startData,
    }
  }

  onStatus?.(`Execution Readiness job started. Job ID: ${job.Id}`)

  let latestJob = job

  for (let attempt = 1; attempt <= 30; attempt += 1) {
    await sleep(2000)

    latestJob = await getJobStatus(uipathSDK, folderId, job.Id)
    const state = latestJob?.State || latestJob?.state || 'Unknown'

    onStatus?.(`Waiting for execution readiness result... Current state: ${state}`)

    if (state === 'Successful') {
      const output = parseExecutionReadinessOutputArguments(latestJob)

      return {
        processingStatus:
          output?.readinessStatus || 'Execution Readiness completed successfully.',
        jobId: job.Id,
        jobKey: job.Key,
        jobState: state,
        output,
        raw: latestJob,
      }
    }

    if (['Faulted', 'Stopped', 'Suspended'].includes(state)) {
      throw new Error(`Execution Readiness job ended with state: ${state}`)
    }
  }

  return {
    processingStatus: 'Execution Readiness job started but output was not available yet.',
    jobId: job.Id,
    jobKey: job.Key,
    jobState: latestJob?.State || 'Unknown',
    raw: latestJob,
  }
}

export async function runTestManagerWriteBackAgent(
  uipathSDK: any,
  input: TestManagerWriteBackInput,
  onStatus?: (message: string) => void
): Promise<TestManagerWriteBackRunResult> {
  const testManagerWriteBackFolderName = requireConfigValue(
    TEST_MANAGER_WRITEBACK_FOLDER_NAME,
    'VITE_UIPATH_TEST_MANAGER_WRITEBACK_FOLDER_NAME'
  )

  const testManagerWriteBackAgentName = requireConfigValue(
    TEST_MANAGER_WRITEBACK_AGENT_NAME,
    'VITE_UIPATH_TEST_MANAGER_WRITEBACK_PROCESS_NAME'
  )

  onStatus?.(`Getting UiPath folder: ${testManagerWriteBackFolderName}`)
  const folderId = await getFolderIdByName(uipathSDK, testManagerWriteBackFolderName)

  onStatus?.(
    `Getting published Test Manager WriteBack agent: ${testManagerWriteBackAgentName}`
  )
  const releaseKey = await getReleaseKeyByName(
    uipathSDK,
    folderId,
    testManagerWriteBackAgentName
  )

  onStatus?.('Starting UiPath Test Manager WriteBack job...')

  let questionPayload: any = buildCompactTestManagerPayload(input)
  let inputArguments = JSON.stringify({
    question: JSON.stringify(questionPayload),
  })

  if (!questionPayload.testManagerProjectKey) {
    throw new Error('UiPath Test Manager Project Key is missing.')
  }

  if (!Array.isArray(questionPayload.testScenarios) || questionPayload.testScenarios.length === 0) {
    throw new Error('No approved Azure DevOps test cases are available for UiPath Test Manager sync.')
  }

  console.log('Test Manager Project Key:', questionPayload.testManagerProjectKey)
  console.log('Test Manager Sync mode:', questionPayload.syncMode)
  console.log('Test Manager testSetMode:', questionPayload.testSetMode)
  console.log('Test Manager Sync testScenarios count:', questionPayload.testScenarios.length)
  console.log('Test Manager first testScenario:', questionPayload.testScenarios[0])
  console.log('Test Manager Sync payload:', questionPayload)
  console.log('Test Manager Sync InputArguments length:', inputArguments.length)

  if (inputArguments.length > 9500) {
    questionPayload = buildFallbackTestManagerPayload(
      input.requirementId,
      questionPayload.testScenarios,
      questionPayload.testManagerProjectKey
    )
    inputArguments = JSON.stringify({
      question: JSON.stringify(questionPayload),
    })
    console.warn('Test Manager Sync payload too large; using fallback payload.')
    console.log('Test Manager Sync payload:', questionPayload)
    console.log('Test Manager Sync InputArguments length:', inputArguments.length)
  }

  if (inputArguments.length > 10000) {
    throw new Error(
      'Test Manager Sync payload is too large. Please reduce selected test cases or sync in batches.'
    )
  }

  const body = {
    startInfo: {
      ReleaseKey: releaseKey,
      Strategy: 'ModernJobsCount',
      JobsCount: 1,
      InputArguments: inputArguments,
    },
  }

  const startData = await orchestratorFetch(
    uipathSDK,
    `/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    },
    folderId
  )

  const job = startData?.value?.[0] || startData?.Value?.[0] || startData?.[0]

  if (!job?.Id) {
    return {
      processingStatus: 'Test Manager WriteBack job started, but job ID was not returned.',
      raw: startData,
    }
  }

  onStatus?.(`Test Manager WriteBack job started. Job ID: ${job.Id}`)

  let latestJob = job

  for (let attempt = 1; attempt <= 30; attempt += 1) {
    await sleep(2000)

    latestJob = await getJobStatus(uipathSDK, folderId, job.Id)
    const state = latestJob?.State || latestJob?.state || 'Unknown'

    onStatus?.(`Waiting for Test Manager sync preparation... Current state: ${state}`)

    if (state === 'Successful') {
      const output = parseTestManagerWriteBackOutputArguments(latestJob)

      return {
        processingStatus:
          output?.syncStatus || 'Test Manager WriteBack completed successfully.',
        jobId: job.Id,
        jobKey: job.Key,
        jobState: state,
        output,
        raw: latestJob,
      }
    }

    if (['Faulted', 'Stopped', 'Suspended'].includes(state)) {
      throw new Error(`Test Manager WriteBack job ended with state: ${state}`)
    }
  }

  return {
    processingStatus: 'Test Manager WriteBack job started but output was not available yet.',
    jobId: job.Id,
    jobKey: job.Key,
    jobState: latestJob?.State || 'Unknown',
    raw: latestJob,
  }
}

export async function runAutomationLinkAgent(
  uipathSDK: any,
  input: AutomationLinkInput,
  onStatus?: (message: string) => void
): Promise<AutomationLinkRunResult> {
  const automationLinkFolderName = requireConfigValue(
    AUTOMATION_LINK_FOLDER_NAME,
    'VITE_UIPATH_AUTOMATION_LINK_FOLDER_NAME'
  )

  const automationLinkAgentName = requireConfigValue(
    AUTOMATION_LINK_AGENT_NAME,
    'VITE_UIPATH_AUTOMATION_LINK_PROCESS_NAME'
  )

  onStatus?.('Preparing UiPath folder context...')
  const folderId = await getFolderIdByName(uipathSDK, automationLinkFolderName)

  onStatus?.('Getting published Automation Link agent...')
  const releaseKey = await getReleaseKeyByName(
    uipathSDK,
    folderId,
    automationLinkAgentName
  )

  onStatus?.('Starting Automation Link job...')

  const questionPayload = {
    operation: 'LINK_AUTOMATION_TO_TEST_CASES',
    projectId: input.projectId,
    createdTestCaseIds: input.createdTestCaseIds,
    packageIdentifier: input.packageIdentifier,
    automationMappings: input.automationMappings || [],
    source: 'QualityOps UI',
  }

  const body = {
    startInfo: {
      ReleaseKey: releaseKey,
      Strategy: 'ModernJobsCount',
      JobsCount: 1,
      InputArguments: JSON.stringify({
        question: JSON.stringify(questionPayload),
      }),
    },
  }

  const startData = await orchestratorFetch(
    uipathSDK,
    `/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    },
    folderId
  )

  const job = startData?.value?.[0] || startData?.Value?.[0] || startData?.[0]

  if (!job?.Id) {
    return {
      processingStatus: 'Automation Link job started, but job ID was not returned.',
      raw: startData,
    }
  }

  onStatus?.(`Automation Link job started. Job ID: ${job.Id}`)

  let latestJob = job

  for (let attempt = 1; attempt <= 30; attempt += 1) {
    await sleep(2000)

    latestJob = await getJobStatus(uipathSDK, folderId, job.Id)
    const state = latestJob?.State || latestJob?.state || 'Unknown'

    onStatus?.(`Waiting for automation mapping result... Current state: ${state}`)

    if (state === 'Successful') {
      const output = parseAutomationLinkOutputArguments(latestJob)

      return {
        processingStatus:
          output?.automationLinkStatus || 'Automation Link completed successfully.',
        jobId: job.Id,
        jobKey: job.Key,
        jobState: state,
        output,
        raw: latestJob,
      }
    }

    if (['Faulted', 'Stopped', 'Suspended'].includes(state)) {
      throw new Error(`Automation Link job ended with state: ${state}`)
    }
  }

  return {
    processingStatus: 'Automation Link job started but output was not available yet.',
    jobId: job.Id,
    jobKey: job.Key,
    jobState: latestJob?.State || 'Unknown',
    raw: latestJob,
  }
}

export async function runTestResultTriageAgent(
  uipathSDK: any,
  input: TestResultTriageInput,
  onStatus?: (message: string) => void
): Promise<TestResultTriageRunResult> {
  const testResultTriageFolderName = requireConfigValue(
    TEST_RESULT_TRIAGE_FOLDER_NAME,
    'VITE_UIPATH_TEST_RESULT_TRIAGE_FOLDER_NAME'
  )

  const testResultTriageAgentName = requireConfigValue(
    TEST_RESULT_TRIAGE_AGENT_NAME,
    'VITE_UIPATH_TEST_RESULT_TRIAGE_PROCESS_NAME'
  )

  onStatus?.('Preparing UiPath folder context...')
  const folderId = await getFolderIdByName(uipathSDK, testResultTriageFolderName)

  onStatus?.('Getting published Test Result Triage agent...')
  const releaseKey = await getReleaseKeyByName(
    uipathSDK,
    folderId,
    testResultTriageAgentName
  )

  onStatus?.('Starting Test Result Triage job...')

  const body = {
    startInfo: {
      ReleaseKey: releaseKey,
      Strategy: 'ModernJobsCount',
      JobsCount: 1,
      InputArguments: JSON.stringify({
        question: JSON.stringify(input),
      }),
    },
  }

  const startData = await orchestratorFetch(
    uipathSDK,
    `/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    },
    folderId
  )

  const job = startData?.value?.[0] || startData?.Value?.[0] || startData?.[0]

  if (!job?.Id) {
    return {
      processingStatus: 'Test Result Triage job started, but job ID was not returned.',
      raw: startData,
    }
  }

  onStatus?.(`Test Result Triage job started. Job ID: ${job.Id}`)

  let latestJob = job

  for (let attempt = 1; attempt <= 30; attempt += 1) {
    await sleep(2000)

    latestJob = await getJobStatus(uipathSDK, folderId, job.Id)
    const state = latestJob?.State || latestJob?.state || 'Unknown'

    onStatus?.(`Waiting for Test Result Triage result... Current state: ${state}`)

    if (state === 'Successful') {
      const output = parseTestResultTriageOutputArguments(latestJob)

      return {
        processingStatus:
          output?.status ||
          output?.defectCreationStatus ||
          'Test Result Triage completed successfully.',
        jobId: job.Id,
        jobKey: job.Key,
        jobState: state,
        output,
        raw: latestJob,
      }
    }

    if (['Faulted', 'Stopped', 'Suspended'].includes(state)) {
      throw new Error(`Test Result Triage job ended with state: ${state}`)
    }
  }

  return {
    processingStatus: 'Test Result Triage job started but output was not available yet.',
    jobId: job.Id,
    jobKey: job.Key,
    jobState: latestJob?.State || 'Unknown',
    raw: latestJob,
  }
}

export async function runFinalReportMailAgent(
  uipathSDK: any,
  input: FinalReportMailInput,
  onStatus?: (message: string) => void
): Promise<FinalReportMailRunResult> {
  const finalReportMailFolderName = requireConfigValue(
    FINAL_REPORT_MAIL_FOLDER_NAME,
    'VITE_UIPATH_FINAL_REPORT_MAIL_FOLDER_NAME'
  )

  const finalReportMailAgentName = requireConfigValue(
    FINAL_REPORT_MAIL_AGENT_NAME,
    'VITE_UIPATH_FINAL_REPORT_MAIL_PROCESS_NAME'
  )

  onStatus?.('Preparing UiPath folder context...')
  const folderId = await getFolderIdByName(uipathSDK, finalReportMailFolderName)

  onStatus?.('Getting published Final QA Report Mail agent...')
  const releaseKey = await getReleaseKeyByName(
    uipathSDK,
    folderId,
    finalReportMailAgentName
  )

  onStatus?.('Starting Final QA Report Mail job...')

  const body = {
    startInfo: {
      ReleaseKey: releaseKey,
      Strategy: 'ModernJobsCount',
      JobsCount: 1,
      InputArguments: JSON.stringify({
        question: JSON.stringify(input),
        variationId: '',
      }),
    },
  }

  const startData = await orchestratorFetch(
    uipathSDK,
    `/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    },
    folderId
  )

  const job = startData?.value?.[0] || startData?.Value?.[0] || startData?.[0]

  if (!job?.Id) {
    return {
      processingStatus: 'Final QA Report Mail job started, but job ID was not returned.',
      raw: startData,
    }
  }

  onStatus?.(`Final QA Report Mail job started. Job ID: ${job.Id}`)

  let latestJob = job

  for (let attempt = 1; attempt <= 30; attempt += 1) {
    await sleep(2000)

    latestJob = await getJobStatus(uipathSDK, folderId, job.Id)
    const state = latestJob?.State || latestJob?.state || 'Unknown'

    onStatus?.(`Waiting for Final QA Report Mail result... Current state: ${state}`)

    if (state === 'Successful') {
      const output = parseFinalReportMailOutputArguments(latestJob)
      const blockedReasons = output?.blockedReasons
      const outputStatus = (output?.status || output?.mailStatus || output?.emailStatus || '').toLowerCase()

      if (
        outputStatus.includes('error') ||
        outputStatus.includes('failed') ||
        blockedReasons?.length
      ) {
        throw new Error(
          output?.errorMessage ||
            output?.message ||
            blockedReasons?.join(' ') ||
            'Final QA Report Mail agent returned an error.'
        )
      }

      return {
        processingStatus:
          output?.message ||
          output?.mailStatus ||
          output?.emailStatus ||
          output?.status ||
          'Final QA report email sent successfully.',
        jobId: job.Id,
        jobKey: job.Key,
        jobState: state,
        output,
        raw: latestJob,
      }
    }

    if (['Faulted', 'Stopped', 'Suspended'].includes(state)) {
      const output = parseFinalReportMailOutputArguments(latestJob)
      throw new Error(
        output?.errorMessage ||
          output?.message ||
          output?.blockedReasons?.join(' ') ||
          `Final QA Report Mail job ended with state: ${state}`
      )
    }
  }

  return {
    processingStatus: 'Final QA Report Mail job started but output was not available yet.',
    jobId: job.Id,
    jobKey: job.Key,
    jobState: latestJob?.State || 'Unknown',
    raw: latestJob,
  }
}
