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

const ORCHESTRATOR_URL = import.meta.env.VITE_UIPATH_ORCHESTRATOR_URL
const FOLDER_NAME = import.meta.env.VITE_UIPATH_FOLDER_NAME
const REQUIREMENT_AGENT_NAME = import.meta.env.VITE_UIPATH_REQUIREMENT_AGENT_NAME

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

  if (folderId) {
    headers['X-UIPATH-OrganizationUnitId'] = String(folderId)
  }

  const url = `${ORCHESTRATOR_URL}${path}`
  console.log('Calling Orchestrator URL:', url)

  const response = await fetch(url, {
    ...options,
    headers,
  })

  const text = await response.text()
  const data = text ? JSON.parse(text) : null

  if (!response.ok) {
    throw new Error(
      data?.message ||
        data?.Message ||
        data?.error?.message ||
        `Orchestrator API failed with status ${response.status}`
    )
  }

  return data
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function parseOutputArguments(jobData: any): RequirementAgentOutput | undefined {
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

export async function getFolderId(uipathSDK: any): Promise<number> {
  const encodedName = FOLDER_NAME.replace(/'/g, "''")

  const data = await orchestratorFetch(
    uipathSDK,
    `/odata/Folders?$filter=DisplayName eq '${encodedName}'`
  )

  const folder = data?.value?.[0]

  if (!folder?.Id) {
    throw new Error(`Folder not found: ${FOLDER_NAME}`)
  }

  return folder.Id
}

export async function getReleaseKey(uipathSDK: any, folderId: number): Promise<string> {
  const encodedName = REQUIREMENT_AGENT_NAME.replace(/'/g, "''")

  const data = await orchestratorFetch(
    uipathSDK,
    `/odata/Releases?$filter=Name eq '${encodedName}'`,
    {},
    folderId
  )

  const release = data?.value?.[0]

  if (!release?.Key) {
    throw new Error(`Published agent/process not found: ${REQUIREMENT_AGENT_NAME}`)
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
  onStatus?.('Getting UiPath folder...')
  const folderId = await getFolderId(uipathSDK)

  onStatus?.('Getting published coded agent...')
  const releaseKey = await getReleaseKey(uipathSDK, folderId)

  onStatus?.('Starting coded agent job...')

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
      processingStatus: 'Job started, but job ID was not returned.',
      raw: startData,
    }
  }

  onStatus?.(`Job started. Job ID: ${job.Id}`)

  let latestJob = job

  for (let attempt = 1; attempt <= 30; attempt += 1) {
    await sleep(2000)

    latestJob = await getJobStatus(uipathSDK, folderId, job.Id)
    const state = latestJob?.State || latestJob?.state || 'Unknown'

    onStatus?.(`Waiting for coded agent result... Current state: ${state}`)

    if (state === 'Successful') {
      const output = parseOutputArguments(latestJob)

      return {
        processingStatus: output?.processingStatus || 'Coded agent completed successfully.',
        jobId: job.Id,
        jobKey: job.Key,
        jobState: state,
        output,
        raw: latestJob,
      }
    }

    if (['Faulted', 'Stopped', 'Suspended'].includes(state)) {
      throw new Error(`Coded agent job ended with state: ${state}`)
    }
  }

  return {
    processingStatus: 'Coded agent job started but output was not available yet.',
    jobId: job.Id,
    jobKey: job.Key,
    jobState: latestJob?.State || 'Unknown',
    raw: latestJob,
  }
}