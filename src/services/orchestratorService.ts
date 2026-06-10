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
  requirementId: string
  decisionType: string
  decisionComment: string
  submittedBy: string
  environment: string
}

export type AdoWriteBackOutput = {
  writeBackStatus?: string
  requirementId?: string
  decisionType?: string
  commentText?: string
}

export type AdoWriteBackRunResult = {
  processingStatus: string
  jobId?: number
  jobKey?: string
  jobState?: string
  output?: AdoWriteBackOutput
  raw?: unknown
}

export type TestScenarioGenerationInput = {
  requirementId: string
  submittedBy: string
  environment: string
  requirementTitle?: string
  requirementDescription?: string
  acceptanceCriteria?: string
  riskLevel?: string
  testingScope?: string[]
  suggestedTestFocus?: string[]
}

export type TestScenario = {
  scenarioId?: string
  scenarioTitle?: string
  priority?: string
  testType?: string
  preconditions?: string[]
  steps?: string[]
  expectedResult?: string
}

export type TestScenarioGenerationOutput = {
  generationStatus?: string
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
    throw new Error(
      data?.message ||
        data?.Message ||
        data?.error?.message ||
        data?.error?.Message ||
        `Orchestrator API failed with status ${response.status}`
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

function parseTestScenarioGenerationOutputArguments(
  jobData: any
): TestScenarioGenerationOutput | undefined {
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
      generationStatus: String(outputArguments),
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
  return await orchestratorFetch(uipathSDK, `/odata/Jobs(${jobId})`, {}, folderId)
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
    requirementId: input.requirementId,
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

      return {
        processingStatus: output?.writeBackStatus || 'ADO WriteBack completed successfully.',
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

  for (let attempt = 1; attempt <= 30; attempt += 1) {
    await sleep(2000)

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
    processingStatus: 'Test Scenario Generation job started but output was not available yet.',
    jobId: job.Id,
    jobKey: job.Key,
    jobState: latestJob?.State || 'Unknown',
    raw: latestJob,
  }
}
