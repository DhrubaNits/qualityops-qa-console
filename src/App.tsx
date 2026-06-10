import { useMemo, useState } from 'react'
import { AuthProvider, useAuth } from './context/AuthContext'
import { LoginScreen } from './components/LoginScreen'
import {
  runRequirementAgent,
  runAdoWriteBackAgent,
  type RequirementAgentOutput,
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
  | 'Peer Review'
  | 'Release Readiness'

type RunStatus = 'Idle' | 'Ready' | 'Running' | 'Completed' | 'Error'

type DecisionStatus = 'Idle' | 'Updating' | 'Updated' | 'Error'

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
  const [decisionStatus, setDecisionStatus] = useState<DecisionStatus>('Idle')

  const modules = useMemo(
    () => [
      {
        title: 'Requirement Analysis',
        description: 'Fetch requirement, identify gaps, and prepare QA readiness summary.',
        status: 'Active',
      },
      {
        title: 'Test Generation',
        description: 'Generate test scenarios and test cases from approved requirements.',
        status: 'Coming soon',
      },
      {
        title: 'Test Execution',
        description: 'Trigger test execution and monitor run status from one place.',
        status: 'Coming soon',
      },
      {
        title: 'Peer Review',
        description: 'Route generated QA artifacts for peer or QA Lead review.',
        status: 'Coming soon',
      },
      {
        title: 'Release Readiness',
        description: 'Summarize QA quality, risk, coverage, failures, and readiness.',
        status: 'Coming soon',
      },
    ],
    []
  )

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

  const handleRun = async () => {
    if (!requirementId.trim() || !submittedBy.trim()) {
      setStatus('Error')
      setStatusMessage('Requirement ID and Submitted By are mandatory.')
      setAgentOutput(null)
      setQaLeadDecision('')
      setDecisionStatus('Idle')
      return
    }

    if (actionType !== 'Requirement Analysis') {
      setStatus('Ready')
      setStatusMessage(`${actionType} module is prepared for future implementation.`)
      setAgentOutput(null)
      setQaLeadDecision('')
      setDecisionStatus('Idle')
      return
    }

    try {
      setStatus('Running')
      setAgentOutput(null)
      setQaLeadDecision('')
      setDecisionStatus('Idle')
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
      setQaLeadDecision('')
      setDecisionStatus('Idle')
      setStatusMessage(error instanceof Error ? error.message : 'Failed to run coded agent job.')
    }
  }

  const handleApprove = async () => {
    if (!requirementId.trim() || !submittedBy.trim()) {
      setStatus('Error')
      setStatusMessage('Requirement ID and Submitted By are mandatory before approval.')
      return
    }

    try {
      setDecisionStatus('Updating')
      setStatus('Running')
      setStatusMessage('Updating ADO with QA Lead approval...')

      const result = await runAdoWriteBackAgent(
        uipathSDK,
        {
          requirementId: requirementId.trim(),
          submittedBy: submittedBy.trim(),
          environment,
          decisionType: 'Approved',
          decisionComment: 'Approved by QA Lead. Requirement is ready for test generation.',
        },
        (message) => {
          setStatusMessage(message)
        }
      )

      setDecisionStatus('Updated')
      setStatus('Completed')
      setQaLeadDecision('Approved by QA Lead. Requirement is ready for test generation.')
      setStatusMessage(
        `${result.processingStatus} Job ID: ${result.jobId ?? 'N/A'}, State: ${
          result.jobState ?? 'N/A'
        }`
      )
    } catch (error) {
      setDecisionStatus('Error')
      setStatus('Error')
      setQaLeadDecision('Approval update failed.')
      setStatusMessage(error instanceof Error ? error.message : 'Failed to update ADO approval.')
    }
  }

  const handleRequestClarification = async () => {
    if (!requirementId.trim() || !submittedBy.trim()) {
      setStatus('Error')
      setStatusMessage('Requirement ID and Submitted By are mandatory before clarification request.')
      return
    }

    try {
      setDecisionStatus('Updating')
      setStatus('Running')
      setStatusMessage('Updating ADO with clarification request...')

      const result = await runAdoWriteBackAgent(
        uipathSDK,
        {
          requirementId: requirementId.trim(),
          submittedBy: submittedBy.trim(),
          environment,
          decisionType: 'Clarification Requested',
          decisionComment:
            'Clarification requested by QA Lead. Requirement needs update before test generation.',
        },
        (message) => {
          setStatusMessage(message)
        }
      )

      setDecisionStatus('Updated')
      setStatus('Ready')
      setQaLeadDecision('Clarification requested by QA Lead. Requirement needs update.')
      setStatusMessage(
        `${result.processingStatus} Job ID: ${result.jobId ?? 'N/A'}, State: ${
          result.jobState ?? 'N/A'
        }`
      )
    } catch (error) {
      setDecisionStatus('Error')
      setStatus('Error')
      setQaLeadDecision('Clarification update failed.')
      setStatusMessage(
        error instanceof Error ? error.message : 'Failed to update ADO clarification request.'
      )
    }
  }

  const handleGenerateTests = () => {
    setActionType('Test Generation')
    setQaLeadDecision('Moved to Test Generation module.')
    setStatus('Ready')
    setStatusMessage('Test Generation module is prepared for the next phase.')
  }

  const handleClear = () => {
    setActionType('Requirement Analysis')
    setRequirementId('')
    setSubmittedBy('')
    setEnvironment('SQA')
    setStatus('Idle')
    setStatusMessage('Select an action and provide the required details to start.')
    setAgentOutput(null)
    setQaLeadDecision('')
    setDecisionStatus('Idle')
  }

  return (
    <main className="qualityops-app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">Q</div>
          <div>
            <h1>QualityOps</h1>
            <p>QA Console</p>
          </div>
        </div>

        <nav className="nav-list">
          <button className="nav-item active">Dashboard</button>
          <button className="nav-item">Requirement Analysis</button>
          <button className="nav-item">Test Generation</button>
          <button className="nav-item">Test Execution</button>
          <button className="nav-item">Peer Review</button>
          <button className="nav-item">Release Readiness</button>
          <button className="nav-item">Execution History</button>
        </nav>

        <div className="sidebar-card">
          <span className="small-label">Current Phase</span>
          <strong>Phase 1</strong>
          <p>Requirement analysis and QA Lead approval foundation.</p>
        </div>
      </aside>

      <section className="content">
        <header className="page-header">
          <div>
            <span className="eyebrow">AI-powered QA workflow console</span>
            <h2>QualityOps QA Console</h2>
            <p>
              One interface for requirement analysis, test generation, execution, peer review,
              and release readiness.
            </p>
          </div>

          <div className="header-actions">
            <div className={`status-pill ${status.toLowerCase()}`}>{status}</div>
            <button className="logout-button" onClick={logout}>
              Logout
            </button>
          </div>
        </header>

        <section className="metrics-grid">
          <div className="metric-card">
            <span>Total Modules</span>
            <strong>5</strong>
            <p>Requirement to release readiness</p>
          </div>

          <div className="metric-card">
            <span>Active Module</span>
            <strong>1</strong>
            <p>Requirement Analysis</p>
          </div>

          <div className="metric-card">
            <span>Environment</span>
            <strong>{environment}</strong>
            <p>Selected execution target</p>
          </div>

          <div className="metric-card">
            <span>QA Status</span>
            <strong>{status}</strong>
            <p>Current workflow state</p>
          </div>
        </section>

        <section className="main-grid">
          <div className="panel">
            <div className="panel-header">
              <h3>Run QA Workflow</h3>
              <p>Select an action and provide input details.</p>
            </div>

            <div className="form-grid">
              <label>
                Action Type
                <select
                  value={actionType}
                  onChange={(event) => setActionType(event.target.value as QaAction)}
                >
                  <option>Requirement Analysis</option>
                  <option>Test Generation</option>
                  <option>Test Execution</option>
                  <option>Peer Review</option>
                  <option>Release Readiness</option>
                </select>
              </label>

              <label>
                Environment
                <select value={environment} onChange={(event) => setEnvironment(event.target.value)}>
                  <option>DEV</option>
                  <option>SQA</option>
                  <option>UAT</option>
                  <option>Production</option>
                </select>
              </label>

              <label>
                Requirement ID <span>*</span>
                <input
                  value={requirementId}
                  onChange={(event) => setRequirementId(event.target.value)}
                  placeholder="Enter requirement ID"
                />
              </label>

              <label>
                Submitted By <span>*</span>
                <input
                  value={submittedBy}
                  onChange={(event) => setSubmittedBy(event.target.value)}
                  placeholder="Enter submitter name"
                />
              </label>
            </div>

            <div className="button-row">
              <button className="primary-button" onClick={handleRun} disabled={status === 'Running'}>
                {status === 'Running' ? 'Running...' : 'Run Selected QA Action'}
              </button>

              <button className="secondary-button" onClick={handleClear}>
                Clear
              </button>
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">
              <h3>Execution Status</h3>
              <p>Live workflow status and next action.</p>
            </div>

            <div className={`result-box ${status.toLowerCase()}`}>
              <strong>{status}</strong>
              <p>{statusMessage}</p>
            </div>

            {agentOutput && (
              <div className="agent-output-card">
                <div className="agent-output-header">
                  <div>
                    <span className="small-label">Live Agent Result</span>
                    <h4>Requirement Analysis Output</h4>
                  </div>

                  <span className="score-pill">
                    Score {agentOutput.requirementQualityAnalysis?.readinessScore ?? '-'}
                  </span>
                </div>

                <div className="summary-grid">
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
                    <strong>
                      {agentOutput.requirementQualityAnalysis?.approvalRecommendation || '-'}
                    </strong>
                  </div>
                </div>

                <div className="output-section">
                  <span>Requirement Title</span>
                  <p>{agentOutput.requirementTitle || '-'}</p>
                </div>

                <div className="output-section">
                  <span>Next Step</span>
                  <p>{agentOutput.qaAnalysisSummary?.nextStep || '-'}</p>
                </div>

                <div className="output-section">
                  <span>Identified Gaps</span>
                  {agentOutput.requirementQualityAnalysis?.identifiedGaps?.length ? (
                    <ul className="gap-list">
                      {agentOutput.requirementQualityAnalysis.identifiedGaps.map((gap, index) => (
                        <li key={`${gap}-${index}`}>{gap}</li>
                      ))}
                    </ul>
                  ) : (
                    <p>No gaps identified.</p>
                  )}
                </div>

                <details className="details-section">
                  <summary>View requirement details</summary>

                  <div className="output-section">
                    <span>Description</span>
                    <p>{agentOutput.requirementDescription || '-'}</p>
                  </div>

                  <div className="output-section">
                    <span>Acceptance Criteria</span>
                    <p>{agentOutput.acceptanceCriteria || '-'}</p>
                  </div>
                </details>

                <div className="qa-lead-actions">
                  <button
                    className="approve-button"
                    onClick={handleApprove}
                    disabled={decisionStatus === 'Updating'}
                  >
                    {decisionStatus === 'Updating' ? 'Updating...' : 'Approve'}
                  </button>

                  <button
                    className="clarify-button"
                    onClick={handleRequestClarification}
                    disabled={decisionStatus === 'Updating'}
                  >
                    Request Clarification
                  </button>

                  <button
                    className="generate-button"
                    onClick={handleGenerateTests}
                    disabled={decisionStatus === 'Updating'}
                  >
                    Generate Test Scenarios
                  </button>
                </div>

                {qaLeadDecision && <div className="qa-lead-decision">{qaLeadDecision}</div>}
              </div>
            )}

            <div className="result-list">
              <div>
                <span>Selected Action</span>
                <strong>{actionType}</strong>
              </div>

              <div>
                <span>Requirement ID</span>
                <strong>{requirementId || '-'}</strong>
              </div>

              <div>
                <span>Submitted By</span>
                <strong>{submittedBy || '-'}</strong>
              </div>

              <div>
                <span>Environment</span>
                <strong>{environment}</strong>
              </div>
            </div>
          </div>
        </section>

        <section className="history-panel">
          <div className="panel-header">
            <h3>Execution History</h3>
            <p>Recent QualityOps agent runs from this session.</p>
          </div>

          {executionHistory.length === 0 ? (
            <div className="empty-history">
              No execution history yet. Run requirement analysis to populate this section.
            </div>
          ) : (
            <div className="history-card-list">
              {executionHistory.map((item, index) => (
                <article
                  className="history-card"
                  key={`${item.requirementId}-${item.timestamp}-${index}`}
                >
                  <div className="history-card-header">
                    <div>
                      <span className="small-label">Requirement</span>
                      <strong>{item.requirementId}</strong>
                    </div>

                    <span className="history-status">{item.readinessStatus}</span>
                  </div>

                  <div className="history-details">
                    <div>
                      <span>Score</span>
                      <strong>{item.readinessScore}</strong>
                    </div>

                    <div>
                      <span>Risk</span>
                      <strong>{item.riskLevel}</strong>
                    </div>

                    <div>
                      <span>Environment</span>
                      <strong>{item.environment}</strong>
                    </div>
                  </div>

                  <div className="history-next-step">
                    <span>Next Step</span>
                    <p>{item.nextStep}</p>
                  </div>

                  <div className="history-footer">
                    <span>Submitted by {item.submittedBy}</span>
                    <span>{item.timestamp}</span>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="module-grid">
          {modules.map((module) => (
            <article
              key={module.title}
              className={`module-card ${module.title === actionType ? 'selected' : ''}`}
              onClick={() => setActionType(module.title as QaAction)}
            >
              <div>
                <h4>{module.title}</h4>
                <p>{module.description}</p>
              </div>

              <span className={module.status === 'Active' ? 'tag active' : 'tag'}>
                {module.status}
              </span>
            </article>
          ))}
        </section>
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