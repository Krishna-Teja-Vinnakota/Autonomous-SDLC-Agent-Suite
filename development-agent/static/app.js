/**
 * Developer Agent V2.0 Frontend Logic - Complete Implementation
 * Updated with validation agent workflow and new HITL points
 */

let currentWorkflowId = null;
let pollingInterval = null;

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    testConfiguration();
});

function initializeEventListeners() {
    // Form submission
    document.getElementById('startWorkflowForm').addEventListener('submit', startWorkflow);
    
    // File approval buttons
    document.getElementById('approveFilesBtn').addEventListener('click', () => approveFiles('approve'));
    document.getElementById('rejectFilesBtn').addEventListener('click', async () => {
        try {
            showLoading('Cancelling workflow...');
            
            await fetch(`/api/workflow/approve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    workflow_id: currentWorkflowId,
                    action: 'reject'
                })
            });
            
            hideLoading();
            showToast('Workflow cancelled', 'info');
            
            // Reset to initial state
            resetToInitialState();
            
        } catch (error) {
            hideLoading();
            showToast('Failed to cancel workflow', 'error');
        }
    });
    
    // Validation approval buttons
    document.getElementById('approveValidationBtn').addEventListener('click', () => approveValidation('approve'));
    document.getElementById('feedbackValidationBtn').addEventListener('click', () => showValidationFeedbackForm());
    // Remove the reject validation button handler - button no longer exists
    
    // Validation feedback form
    document.getElementById('submitValidationFeedbackBtn').addEventListener('click', async () => {
        const feedbackText = document.getElementById('validationFeedback').value.trim();
        
        if (!feedbackText) {
            showToast('Please provide feedback before submitting', 'error');
            return;
        }
        
        try {
            // Hide feedback form and approval buttons
            document.getElementById('validationFeedbackForm').style.display = 'none';
            document.getElementById('approveValidationBtn').style.display = 'none';
            document.getElementById('feedbackValidationBtn').style.display = 'none';
            
            // Show processing state
            showFeedbackProcessingState(feedbackText);
            
            const response = await fetch(`/api/workflow/approve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    workflow_id: currentWorkflowId,
                    action: 'feedback',
                    feedback: feedbackText
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to submit feedback');
            }
            
            // Clear feedback
            document.getElementById('validationFeedback').value = '';
            
            showToast('Feedback submitted - applying changes...', 'success');
            
            // Wait a bit then refresh status to show updated validation
            setTimeout(() => {
                pollWorkflowStatus();
            }, 2000);
            
        } catch (error) {
            console.error('Error submitting feedback:', error);
            showToast('Failed to submit feedback', 'error');
            
            // Restore buttons on error
            document.getElementById('approveValidationBtn').style.display = 'inline-flex';
            document.getElementById('feedbackValidationBtn').style.display = 'inline-flex';
        }
    });
    document.getElementById('cancelValidationFeedbackBtn').addEventListener('click', hideValidationFeedbackForm);
    
    // Other buttons
    document.getElementById('configTestBtn').addEventListener('click', testConfiguration);
    document.getElementById('resetBtn').addEventListener('click', resetWorkflow);
}

async function startWorkflow(event) {
    event.preventDefault();
    
    const jiraTicketId = document.getElementById('jiraTicketId').value.trim();
    const repoPath = document.getElementById('repoPath').value.trim();
    
    if (!jiraTicketId || !repoPath) {
        showToast('Please fill in all required fields', 'error');
        return;
    }
    
    try {
        showLoading('Starting workflow...');
        
        const response = await fetch('/api/workflow/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                jira_ticket_id: jiraTicketId,
                repo_path: repoPath,
                developer_id: 'frontend_user'
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        currentWorkflowId = data.workflow_id;
        
        hideLoading();
        showWorkflowStatus();
        startPolling();
        
        showToast('Workflow started successfully!', 'success');
        
    } catch (error) {
        hideLoading();
        console.error('Error starting workflow:', error);
        showToast('Failed to start workflow: ' + error.message, 'error');
    }
}

async function approveFiles(action) {
    if (!currentWorkflowId) return;
    
    try {
        showLoading(`${action === 'approve' ? 'Approving' : 'Rejecting'} files...`);
        
        const response = await fetch('/api/workflow/approve', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                workflow_id: currentWorkflowId,
                action: action
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        hideLoading();
        
        if (action === 'approve') {
            // Hide file approval buttons and show modification in progress
            hideFileApprovalButtons();
            showModificationInProgress();
            showToast('Files approved! Starting modification...', 'success');
        } else {
            showToast('Workflow cancelled', 'info');
        }
        
    } catch (error) {
        hideLoading();
        console.error('Error approving files:', error);
        showToast('Failed to process approval: ' + error.message, 'error');
    }
}

async function approveValidation(action) {
    if (!currentWorkflowId) return;
    
    try {
        showLoading(`${action === 'approve' ? 'Approving validation' : 'Rejecting changes'}...`);
        
        const response = await fetch('/api/workflow/approve', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                workflow_id: currentWorkflowId,
                action: action
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        hideLoading();
        const message = action === 'approve' ? 'Creating pull request...' : 'Workflow cancelled';
        showToast(message, action === 'approve' ? 'success' : 'info');
        
    } catch (error) {
        hideLoading();
        console.error('Error processing validation approval:', error);
        showToast('Failed to process validation: ' + error.message, 'error');
    }
}

function showValidationFeedbackForm() {
    document.getElementById('validationFeedbackForm').style.display = 'block';
    document.getElementById('validationFeedback').focus();
}

function hideValidationFeedbackForm() {
    document.getElementById('validationFeedbackForm').style.display = 'none';
    document.getElementById('validationFeedback').value = '';
}

// Add this new function to show processing state:
function showFeedbackProcessingState(feedback) {
    const validationSection = document.getElementById('validationSection');
    
    // Create or update processing section
    let processingSection = document.getElementById('feedbackProcessingSection');
    if (!processingSection) {
        processingSection = document.createElement('div');
        processingSection.id = 'feedbackProcessingSection';
        processingSection.className = 'info-section feedback-processing-section';
        validationSection.appendChild(processingSection);
    }
    
    processingSection.innerHTML = `
        <h3>💬 Processing Your Feedback</h3>
        <p class="section-description">Applying your feedback and re-validating changes...</p>
        <div class="feedback-content">
            <div class="feedback-display">
                <h4>Your Feedback:</h4>
                <div class="feedback-text">${feedback}</div>
            </div>
            <div class="processing-loader">
                <div class="loader-small"></div>
                <span>Updating code based on feedback...</span>
            </div>
        </div>
    `;
    
    processingSection.style.display = 'block';
}

async function pollWorkflowStatus() {
    if (!currentWorkflowId) return;
    
    try {
        const response = await fetch(`/api/workflow/${currentWorkflowId}/status`);
        
        if (!response.ok) {
            console.error('Failed to fetch workflow status');
            return;
        }
        
        const status = await response.json();
        updateWorkflowDisplay(status);
        
    } catch (error) {
        console.error('Error polling workflow status:', error);
    }
}

// Add this new function:
function resetToInitialState() {
    // Hide status section and show start section
    document.getElementById('statusSection').style.display = 'none';
    document.getElementById('startSection').style.display = 'block';
    
    // Clear form
    document.getElementById('jiraTicketId').value = '';
    document.getElementById('repoPath').value = '';
    
    // Reset workflow ID
    currentWorkflowId = null;
    
    // Clear any polling
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

function updateWorkflowDisplay(status) {
    // Update workflow ID display
    document.getElementById('workflowId').textContent = status.workflow_id.substring(0, 8);
    
    // Add this case for cancelled workflows:
    if (status.current_stage === 'cancelled') {
        // Reset to initial state
        resetToInitialState();
        showToast('Workflow was cancelled', 'info');
        return;
    }
    
    // Handle feedback processing completion
    if (status.current_stage === 'awaiting_validation_approval') {
        // Check if we're coming back from feedback processing
        const processingSection = document.getElementById('feedbackProcessingSection');
        if (processingSection && processingSection.style.display !== 'none') {
            // Hide processing section
            processingSection.style.display = 'none';
            
            // Show validation section with updated content
            document.getElementById('validationSection').style.display = 'block';
            
            // Show buttons again
            document.getElementById('approveValidationBtn').style.display = 'inline-flex';
            document.getElementById('feedbackValidationBtn').style.display = 'inline-flex';
            
            // Show updated validation results
            if (status.validation_report) {
                updateValidationDisplay(status.validation_report);
            }
            
            showToast('Feedback processed - please review updated changes', 'info');
        }
    }
    
    // Update stage indicators
    updateStageIndicators(status.current_stage);
    
    // Update content based on current stage
    switch (status.current_stage) {
        case 'jira_fetched':
            showJiraDetails(status.jira_content);
            break;
            
        case 'session_ready':
            showIndexingSection();
            break;
            
        case 'files_identified':
            showSearchingSection();
            break;
            
        case 'awaiting_file_approval':
            showFileAnalysis(status.identified_files, status.file_analysis);
            break;
            
        case 'code_modified':
            showModificationSection(status.modifications);
            break;
            
        case 'validated':
        case 'awaiting_validation_approval':
            showValidationSection(status.validation_report);
            // Handle validation stages properly
            const approveBtn = document.getElementById('approveValidationBtn');
            const feedbackBtn = document.getElementById('feedbackValidationBtn');
            
            if (approveBtn) approveBtn.style.display = 'inline-flex';
            if (feedbackBtn) feedbackBtn.style.display = 'inline-flex';
            
            // Hide reject button if it exists
            const rejectBtn = document.getElementById('rejectValidationBtn');
            if (rejectBtn) rejectBtn.style.display = 'none';
            break;
            
        case 'human_feedback_applied':
            showFeedbackProcessing(status.modification_feedback);
            break;
            
        case 'completed':
            showPRCreated(status.pr_url);
            break;
            
        case 'error':
            showError(status.error_message);
            break;
    }
    
    // Update activity log
    updateActivityLog(status.messages);
}

function updateStageIndicators(currentStage) {
    const stages = document.querySelectorAll('.stage');
    const stageOrder = [
        'initialized', 'jira_fetched', 'session_ready', 'files_identified', 
        'awaiting_file_approval', 'code_modified', 'validated', 
        'awaiting_validation_approval', 'completed'
    ];
    
    const currentIndex = stageOrder.indexOf(currentStage);
    
    stages.forEach((stage, index) => {
        stage.classList.remove('active', 'completed');
        
        if (index < currentIndex) {
            stage.classList.add('completed');
        } else if (index === currentIndex) {
            stage.classList.add('active');
        }
    });
}

function showJiraDetails(jiraContent) {
    hideAllSections();
    
    if (jiraContent) {
        document.getElementById('ticketKey').textContent = jiraContent.key;
        document.getElementById('ticketType').textContent = jiraContent.issue_type;
        document.getElementById('ticketPriority').textContent = jiraContent.priority;
        document.getElementById('ticketStatus').textContent = jiraContent.status;
        document.getElementById('ticketSummary').textContent = jiraContent.summary;
        document.getElementById('ticketDescription').textContent = jiraContent.description || 'No description provided';
        
        document.getElementById('jiraDetails').style.display = 'block';
    }
}

function showIndexingSection() {
    hideAllSections();
    document.getElementById('indexingSection').style.display = 'block';
}

function showSearchingSection() {
    hideAllSections();
    document.getElementById('searchingSection').style.display = 'block';
}

function showSearchResults(searchResults) {
    hideAllSections();
    
    const searchResultsList = document.getElementById('searchResultsList');
    searchResultsList.innerHTML = '';
    
    if (searchResults && searchResults.length > 0) {
        searchResults.forEach((result, index) => {
            const div = document.createElement('div');
            div.className = 'search-result-item';
            div.innerHTML = `
                <div class="result-header">
                    <span class="rank">#${index + 1}</span>
                    <span class="file-name">${result.file_path}</span>
                    <span class="similarity-score">${(result.similarity_score * 100).toFixed(1)}%</span>
                </div>
                <div class="result-summary">${result.file_summary}</div>
            `;
            searchResultsList.appendChild(div);
        });
    }
    
    document.getElementById('searchResultsSection').style.display = 'block';
}

function showFileAnalysis(identifiedFiles, fileAnalysis) {
    hideAllSections();
    
    // Show analysis content
    if (fileAnalysis) {
        document.getElementById('analysisContent').textContent = fileAnalysis;
    }
    
    // Show identified files
    const filesList = document.getElementById('filesList');
    filesList.innerHTML = '';
    
    if (identifiedFiles && identifiedFiles.length > 0) {
        identifiedFiles.forEach(file => {
            const li = document.createElement('li');
            li.className = 'file-item';
            li.innerHTML = `<span class="file-icon">📄</span><span class="file-name">${file}</span>`;
            filesList.appendChild(li);
        });
    }
    
    // Show approval buttons
    showFileApprovalButtons();
    
    document.getElementById('fileAnalysisSection').style.display = 'block';
}

function showModificationSection(modifications) {
    hideAllSections();
    
    if (modifications && Object.keys(modifications).length > 0) {
        // Show progress as complete
        const progressBar = document.getElementById('modificationProgressBar');
        const statusText = document.getElementById('modificationStatus');
        
        progressBar.style.width = '100%';
        statusText.textContent = 'Modification completed successfully!';
        
        // Show modified files list
        const modifiedFilesList = document.getElementById('modifiedFilesList');
        modifiedFilesList.innerHTML = '';
        
        Object.keys(modifications).forEach(file => {
            const div = document.createElement('div');
            div.className = 'modified-file-item';
            div.innerHTML = `
                <span class="file-icon">✅</span>
                <span class="file-name">${file}</span>
                <span class="modification-status">Modified</span>
            `;
            modifiedFilesList.appendChild(div);
        });
        
        document.getElementById('modificationContent').style.display = 'block';
    }
    
    document.getElementById('modificationSection').style.display = 'block';
}

function showValidationSection(validationReport) {
    hideAllSections();
    
    if (validationReport) {
        // Show simplified validation files list
        const validationFilesList = document.getElementById('validationFilesList');
        validationFilesList.innerHTML = '';
        
        if (validationReport.validation_results) {
            Object.keys(validationReport.validation_results).forEach(file => {
                const div = document.createElement('div');
                div.className = 'validation-file-item';
                
                const autoFixed = validationReport.auto_fixes_applied > 0;
                const statusIcon = autoFixed ? '🔧' : '✅';
                const statusText = autoFixed ? 'Auto-fixed' : 'Validated';
                
                div.innerHTML = `
                    <div class="validation-file-header">
                        <span class="file-name">${statusIcon} ${file}</span>
                        <span class="validation-status-badge">${statusText}</span>
                    </div>
                `;
                validationFilesList.appendChild(div);
            });
        }
    }
    
    document.getElementById('validationSection').style.display = 'block';
}

// Add this function to update validation display:
function updateValidationDisplay(validationReport) {
    const validationFilesList = document.getElementById('validationFilesList');
    if (!validationFilesList) return;
    
    validationFilesList.innerHTML = '';
    
    if (validationReport.validation_results) {
        Object.keys(validationReport.validation_results).forEach(file => {
            const fileResult = validationReport.validation_results[file];
            const fileDiv = document.createElement('div');
            fileDiv.className = 'validation-file-result';
            
            const autoFixed = validationReport.auto_fixes_applied > 0;
            const statusIcon = autoFixed ? '🔧' : '✅';
            const statusText = autoFixed ? 'Auto-fixed' : 'Validated';
            
            fileDiv.innerHTML = `
                <div class="file-header">
                    <h4>${file}</h4>
                    <span class="validation-status ${statusText.toLowerCase()}">${statusText}</span>
                </div>
                <div class="file-summary">
                    Issues found: ${fileResult.issues ? fileResult.issues.length : 0} | 
                    Requirements satisfied: ${fileResult.requirements_satisfied ? fileResult.requirements_satisfied.length : 0}
                </div>
                ${fileResult.issues && fileResult.issues.length > 0 ? `
                    <div class="issues-found">
                        <h5>Issues Found:</h5>
                        <ul>${fileResult.issues.map(issue => `<li>${issue.description || issue}</li>`).join('')}</ul>
                    </div>
                ` : ''}
                ${validationReport.auto_fixes_applied > 0 ? `
                    <div class="auto-fixes">
                        <h5>Auto-fixes Applied:</h5>
                        <p>Applied ${validationReport.auto_fixes_applied} automatic fixes</p>
                    </div>
                ` : ''}
            `;
            validationFilesList.appendChild(fileDiv);
        });
    }
}

function showFeedbackProcessing(feedback) {
    hideAllSections();
    
    const feedbackSection = document.getElementById('feedbackProcessingSection');
    feedbackSection.style.display = 'block';
    
    if (feedback) {
        document.getElementById('feedbackDisplay').textContent = feedback;
    }
}

function showPRCreated(prUrl) {
    hideAllSections();
    
    if (prUrl) {
        document.getElementById('prLink').href = prUrl;
        document.getElementById('prSection').style.display = 'block';
        showToast('Pull request created successfully!', 'success');
    }
}

function showError(errorMessage) {
    hideAllSections();
    
    document.getElementById('errorMessage').textContent = errorMessage || 'An unknown error occurred';
    document.getElementById('errorSection').style.display = 'block';
    showToast('Workflow failed: ' + errorMessage, 'error');
}

function hideAllSections() {
    const sections = [
        'jiraDetails', 'indexingSection', 'searchingSection', 'searchResultsSection', 
        'fileAnalysisSection', 'modificationSection', 'validationSection',
        'feedbackProcessingSection', 'prSection', 'errorSection'
    ];
    
    sections.forEach(sectionId => {
        document.getElementById(sectionId).style.display = 'none';
    });
}

function hideFileApprovalButtons() {
    const approvalActions = document.querySelector('#fileAnalysisSection .approval-actions');
    if (approvalActions) {
        approvalActions.style.display = 'none';
    }
}

function showFileApprovalButtons() {
    const approvalActions = document.querySelector('#fileAnalysisSection .approval-actions');
    if (approvalActions) {
        approvalActions.style.display = 'flex';
    }
}

function showModificationInProgress() {
    // Add a progress indicator to the file analysis section
    const fileAnalysisSection = document.getElementById('fileAnalysisSection');
    
    // Remove existing progress indicator if any
    const existingProgress = fileAnalysisSection.querySelector('.modification-progress-indicator');
    if (existingProgress) {
        existingProgress.remove();
    }
    
    const progressDiv = document.createElement('div');
    progressDiv.className = 'modification-progress-indicator';
    progressDiv.innerHTML = `
        <div class="progress-status">
            <div class="progress-icon">🔧</div>
            <div class="progress-text">
                <h4>Modifying Files...</h4>
                <p>Please wait while we modify the selected files based on JIRA requirements</p>
            </div>
        </div>
        <div class="progress-loader">
            <div class="loader-small"></div>
        </div>
    `;
    
    fileAnalysisSection.appendChild(progressDiv);
}

function updateActivityLog(messages) {
    const activityLog = document.getElementById('activityLog');
    activityLog.innerHTML = '';
    
    if (messages && messages.length > 0) {
        // Remove duplicates and keep only unique messages
        const uniqueMessages = [...new Set(messages)];
        
        // Show last 8 unique messages
        uniqueMessages.slice(-8).forEach(message => {
            const div = document.createElement('div');
            div.className = 'activity-item';
            div.textContent = message;
            activityLog.appendChild(div);
        });
        
        // Scroll to bottom
        activityLog.scrollTop = activityLog.scrollHeight;
    }
}

function startPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
    }
    
    pollingInterval = setInterval(pollWorkflowStatus, 2000);
}

function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

function showWorkflowStatus() {
    document.getElementById('startSection').style.display = 'none';
    document.getElementById('statusSection').style.display = 'block';
}

function resetWorkflow() {
    stopPolling();
    currentWorkflowId = null;
    
    document.getElementById('startSection').style.display = 'block';
    document.getElementById('statusSection').style.display = 'none';
    
    // Reset form
    document.getElementById('startWorkflowForm').reset();
    
    // Hide feedback form if shown
    hideValidationFeedbackForm();
    
    showToast('Workflow reset', 'info');
}

async function testConfiguration() {
    try {
        const response = await fetch('/api/config/test');
        const config = await response.json();
        
        if (config.status === 'configured') {
            showToast('Configuration OK', 'success');
        } else {
            showToast('Configuration incomplete', 'warning');
            console.log('Config details:', config.details);
        }
    } catch (error) {
        console.error('Error testing configuration:', error);
        showToast('Failed to test configuration', 'error');
    }
}

function showLoading(message = 'Processing...') {
    document.getElementById('loadingMessage').textContent = message;
    document.getElementById('loadingOverlay').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loadingOverlay').style.display = 'none';
}

function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    toastContainer.appendChild(toast);
    
    // Show toast
    setTimeout(() => {
        toast.classList.add('show');
    }, 100);
    
    // Hide and remove toast
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            if (toastContainer.contains(toast)) {
                toastContainer.removeChild(toast);
            }
        }, 300);
    }, 4000);
}