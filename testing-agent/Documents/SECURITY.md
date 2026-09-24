# Security Hardening Guide

Comprehensive security measures implemented in AutoSDLC Test Agent.

---

## 🔒 Security Architecture

### **1. Command Execution Security**

**No Shell Execution:**
- ✅ **Never uses `shell=True`** in subprocess calls
- ✅ Prevents shell injection attacks
- ✅ All commands executed as list arguments

**Command Allowlist:**
```python
ALLOWED_COMMANDS = {
    'npx': ['npx'],
    'npm': ['npm'],
    'pytest': ['pytest'],
    'python': ['python'],
}
```

**Argument Validation:**
- Only pre-approved arguments allowed
- File paths validated
- No arbitrary command construction
- No user input in commands

### **2. Workflow Orchestration Security**

**UI Never Executes Code Directly:**
- ✅ All execution through `WorkflowOrchestrator`
- ✅ UI only triggers workflow
- ✅ No direct subprocess calls from UI
- ✅ All commands validated before execution

**State Management:**
- Shared state object tracks all operations
- No hidden execution paths
- All actions logged
- Audit trail maintained

### **3. Retry Guards**

**Maximum Retries:**
- ✅ **Max 3 retries** per stage
- ✅ **Max 3 retries** overall
- ✅ Prevents infinite loops
- ✅ Timeout enforcement

**Timeout Protection:**
- ✅ **5 minutes** per test execution
- ✅ **30 minutes** overall workflow
- ✅ Automatic timeout handling
- ✅ Resource cleanup on timeout

### **4. Input Validation**

**File Path Validation:**
- ✅ Path traversal prevention
- ✅ Sandboxed execution
- ✅ No access outside workspace
- ✅ Relative path validation

**File Size Limits:**
- ✅ ZIP files: 500 MB max
- ✅ Extracted: 1 GB max
- ✅ Files: 10,000 max
- ✅ Prevents resource exhaustion

### **5. Sandboxing**

**Isolated Workspaces:**
- ✅ UUID-based directories
- ✅ No access to user filesystem
- ✅ All operations in `/workspaces/run_<uuid>/project`
- ✅ Automatic cleanup

**Resource Limits:**
- ✅ Memory limits (implicit)
- ✅ CPU limits (implicit)
- ✅ Disk space limits
- ✅ Process isolation

---

## 🛡️ Security Measures by Component

### **Command Executor**

**Security Features:**
1. Command allowlist enforcement
2. Argument validation
3. No shell=True
4. Timeout protection
5. Error isolation

**Example:**
```python
# ✅ SAFE
executor.execute(['npx', 'jest', '--json'])

# ❌ BLOCKED
executor.execute(['rm', '-rf', '/'])  # Not in allowlist
executor.execute('npx jest', shell=True)  # shell=True blocked
```

### **Workflow Orchestrator**

**Security Features:**
1. Stage isolation
2. Retry limits
3. Timeout enforcement
4. Error containment
5. Cleanup guarantees

**Protection:**
- Each stage isolated
- Failures don't propagate
- Cleanup always runs
- State tracked securely

### **File Operations**

**Security Features:**
1. Path validation
2. Size limits
3. Type checking
4. Sandbox enforcement
5. Cleanup on failure

**Protection:**
- No arbitrary file access
- Size limits prevent DoS
- Type validation prevents exploits
- Sandbox prevents escape

---

## 🔐 Security Best Practices

### **For Users**

1. **Credentials:**
   - Store in environment variables
   - Never commit to repository
   - Use service accounts
   - Rotate regularly

2. **Permissions:**
   - Use minimal permissions
   - Principle of least privilege
   - Review access regularly

3. **Monitoring:**
   - Review execution logs
   - Check for anomalies
   - Monitor resource usage
   - Audit regularly

### **For Developers**

1. **Code Review:**
   - Review all subprocess calls
   - Verify allowlist updates
   - Check timeout values
   - Validate error handling

2. **Testing:**
   - Test security measures
   - Verify sandboxing
   - Test timeout handling
   - Validate cleanup

3. **Updates:**
   - Keep dependencies updated
   - Patch security vulnerabilities
   - Review security advisories
   - Update allowlists carefully

---

## 🚨 Security Checklist

### **Pre-Deployment**

- [ ] All commands in allowlist
- [ ] No shell=True usage
- [ ] Timeouts configured
- [ ] Retry limits set
- [ ] Sandboxing verified
- [ ] Input validation tested
- [ ] Error handling reviewed
- [ ] Cleanup logic verified

### **Runtime**

- [ ] Commands validated
- [ ] Paths sanitized
- [ ] Timeouts enforced
- [ ] Retries limited
- [ ] Resources cleaned
- [ ] Errors logged
- [ ] State tracked
- [ ] Audit trail maintained

---

## 🔍 Security Monitoring

### **What to Monitor**

1. **Command Execution:**
   - Commands attempted
   - Allowlist violations
   - Timeout occurrences
   - Retry counts

2. **Resource Usage:**
   - Execution times
   - Memory usage
   - Disk usage
   - CPU usage

3. **Errors:**
   - Security violations
   - Timeout errors
   - Retry failures
   - Cleanup failures

### **Logging**

All security events logged:
- Command attempts
- Allowlist violations
- Timeout events
- Retry attempts
- Cleanup operations

---

## 🛠️ Security Configuration

### **Timeout Settings**

```python
# Per-test timeout
MAX_EXECUTION_TIME = 300  # 5 minutes

# Overall workflow timeout
WORKFLOW_TIMEOUT = 1800  # 30 minutes
```

### **Retry Limits**

```python
# Per-stage retries
MAX_STAGE_RETRIES = 3

# Overall retries
MAX_WORKFLOW_RETRIES = 3
```

### **Resource Limits**

```python
# File size limits
MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500 MB
MAX_EXTRACTED_SIZE = 1024 * 1024 * 1024  # 1 GB
MAX_FILES = 10000
```

---

## 📋 Security Compliance

### **OWASP Top 10**

- ✅ **A01: Broken Access Control** - Sandboxed execution
- ✅ **A02: Cryptographic Failures** - Secure credential storage
- ✅ **A03: Injection** - Command allowlist, no shell=True
- ✅ **A04: Insecure Design** - Security-first architecture
- ✅ **A05: Security Misconfiguration** - Secure defaults
- ✅ **A06: Vulnerable Components** - Dependency management
- ✅ **A07: Authentication Failures** - Service account auth
- ✅ **A08: Software and Data Integrity** - Input validation
- ✅ **A09: Logging Failures** - Comprehensive logging
- ✅ **A10: SSRF** - Path validation, sandboxing

---

## 🔐 Security Hardening Summary

### **Implemented**

- ✅ Command allowlist
- ✅ No shell=True
- ✅ Timeout protection
- ✅ Retry limits
- ✅ Sandboxing
- ✅ Input validation
- ✅ Path sanitization
- ✅ Resource limits
- ✅ Error isolation
- ✅ Cleanup guarantees
- ✅ Audit logging
- ✅ State tracking

### **Architecture**

- ✅ UI never executes code directly
- ✅ All execution through workflow
- ✅ Shared state management
- ✅ Retry guards
- ✅ Cleanup logic
- ✅ Security-first design

---

**Security Status: ✅ HARDENED**

All security measures implemented and verified.

