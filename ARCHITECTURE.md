# Modal GitOps Operator Architecture

## System Overview

```mermaid
graph TB
    subgraph "Kubernetes Cluster"
        CRD[ModalDeployment CRD]
        Operator[Modal GitOps Operator]
        Secret[Kubernetes Secrets]
    end

    subgraph "Git Repository"
        GitRepo[modal-apps/app.py]
    end

    subgraph "Modal Platform"
        ModalAPI[Modal API]
        DeployedApp[Deployed Modal App]
    end

    CRD -->|Watches| Operator
    Operator -->|Clones| GitRepo
    Operator -->|Deploys via CLI| ModalAPI
    Operator -->|Queries for App ID| ModalAPI
    ModalAPI -->|Manages| DeployedApp
    Operator -->|Updates Status| CRD
    Secret -->|Provides Credentials| Operator

    style Operator fill:#4CAF50
    style CRD fill:#2196F3
    style DeployedApp fill:#FF9800
```

## Deployment Flow

```mermaid
sequenceDiagram
    participant User
    participant K8s as Kubernetes API
    participant Op as Modal Operator
    participant Git as Git Repository  
    participant Modal as Modal Platform

    User->>K8s: kubectl apply -f deployment.yaml
    K8s->>K8s: Create ModalDeployment CRD
    K8s->>Op: Trigger CREATE event

    Op->>K8s: Update status: "Deploying"
    Op->>Git: Clone repository
    Git-->>Op: Return source code

    Op->>Op: Extract app name from Python file<br/>pattern: App("name")

    Op->>Modal: modal deploy app.py
    Modal-->>Op: Deployment successful

    Note over Op,Modal: Wait 2 seconds for app registration

    Op->>Modal: modal app list --json
    Modal-->>Op: Return deployed apps list<br/>[{App ID, Description, State}]

    Op->>Op: Find app by name<br/>Extract App ID (ap-xxxxx)

    Op->>K8s: Update status:<br/>- modalAppId: ap-xxxxx<br/>- url: https://...<br/>- phase: "Ready"

    K8s-->>User: ModalDeployment Ready
```

## Update Flow

```mermaid
sequenceDiagram
    participant User
    participant K8s as Kubernetes API
    participant Op as Modal Operator
    participant Git as Git Repository
    participant Modal as Modal Platform

    User->>K8s: kubectl apply -f updated-deployment.yaml
    K8s->>Op: Trigger UPDATE event

    Op->>K8s: Update status: "Deploying"
    Op->>Git: Clone repository (new commit)
    Git-->>Op: Return updated source code

    Op->>Modal: modal deploy app.py<br/>(updates existing app)
    Modal-->>Op: Deployment successful

    Op->>Modal: modal app list --json
    Modal-->>Op: Return apps with new App ID

    Op->>Op: Extract new App ID

    Op->>K8s: Update status:<br/>- modalAppId: ap-yyyyy (new)<br/>- lastDeployment: <timestamp>

    K8s-->>User: ModalDeployment Updated
```

## Deletion Flow

```mermaid
sequenceDiagram
    participant User
    participant K8s as Kubernetes API
    participant Op as Modal Operator
    participant Modal as Modal Platform

    User->>K8s: kubectl delete modaldeployment my-app
    K8s->>Op: Trigger DELETE event

    Op->>K8s: Update status: "Terminating"

    alt App ID in CRD Status
        Op->>Op: Retrieve modalAppId from status
        Note over Op: Fast path - no API call needed
    else App ID in Memory
        Op->>Op: Retrieve from in-memory cache
    else Need to Query Modal
        Op->>Op: Extract app name from source
        Op->>Modal: modal app list --json
        Modal-->>Op: Return deployed apps
        Op->>Op: Find app ID by name
    end

    Op->>Modal: modal app stop <app-id>
    Modal-->>Op: App stopped

    Op->>Op: Clean up local resources<br/>(delete cloned repo)

    Op->>K8s: Allow deletion to complete
    K8s-->>User: ModalDeployment Deleted
```

## Component Architecture

```mermaid
graph LR
    subgraph "Operator Pod"
        Main[main.py<br/>Kopf Event Handlers]
        Controller[modal_controller.py<br/>Business Logic]
        Utils[utils.py<br/>Helpers]
        Health[health_server.py<br/>HTTP Health Checks]

        Main -->|Calls| Controller
        Main -->|Uses| Utils
        Main -->|Starts| Health
        Controller -->|Uses| Utils
    end

    subgraph "External Systems"
        K8sAPI[Kubernetes API]
        GitSys[Git Repositories]
        ModalCLI[Modal CLI]
    end

    Main -.->|Watches CRDs| K8sAPI
    Controller -->|Clones| GitSys
    Controller -->|Executes| ModalCLI
    ModalCLI -->|Communicates| ModalPlatform[Modal Platform]

    style Main fill:#4CAF50
    style Controller fill:#2196F3
    style Health fill:#FF9800
```

## Data Flow

```mermaid
graph TD
    A[User Applies CRD] --> B{Operator Receives Event}
    B -->|CREATE| C[Clone Git Repo]
    B -->|UPDATE| C
    B -->|DELETE| D[Get App ID]

    C --> E[Extract App Name from Source]
    E --> F[Deploy to Modal]
    F --> G[Wait 2s]
    G --> H[Query Modal for App ID]
    H --> I[Store App ID in CRD Status]
    I --> J[Update Status: Ready]

    D --> K{App ID Source}
    K -->|From CRD Status| L[Use Stored App ID]
    K -->|From Memory| L
    K -->|Query Modal| M[List Apps & Find by Name]
    M --> L

    L --> N[Stop Modal App]
    N --> O[Cleanup Resources]
    O --> P[Complete Deletion]

    style C fill:#E3F2FD
    style F fill:#C8E6C9
    style H fill:#FFF9C4
    style L fill:#FFCCBC
    style N fill:#F8BBD0
```

## Key Design Decisions

### 1. App ID Storage

**Problem**: User's Modal app name may differ from CRD `appName`  
**Solution**: Extract actual app name from Python file and query Modal API for app ID  
**Benefit**: Reliable deletion even when names don't match

### 2. Deployment Strategy

**Problem**: Need to deploy user's Modal apps without modification  
**Solution**: Use `modal deploy` directly on user's file  
**Benefit**: Full Modal feature support, no wrapper code needed

### 3. Deletion Reliability

**Problem**: Operator restarts lose in-memory state  
**Solution**: Store app ID in CRD status (persisted in etcd)  
**Benefit**: Deletion works across operator restarts

### 4. Private Repository Support

**Problem**: Users need access to private Git repos  
**Solution**: Support both SSH keys and Personal Access Tokens via Kubernetes secrets  
**Benefit**: Secure credential management using Kubernetes native secrets

## Security Considerations

```mermaid
graph TB
    subgraph "Security Boundaries"
        ModalCreds[Modal Credentials<br/>Kubernetes Secret]
        GitCreds[Git Credentials<br/>Kubernetes Secret]
        OpPod[Operator Pod<br/>Non-root user]
        RBAC[RBAC Rules<br/>Least Privilege]
    end

    ModalCreds -->|Environment Vars| OpPod
    GitCreds -->|Mounted Secret| OpPod
    RBAC -->|Limits| OpPod

    style ModalCreds fill:#FFCDD2
    style GitCreds fill:#FFCDD2
    style RBAC fill:#C5CAE9
```

### Security Features

1. **Non-root Execution**: Operator runs as user `operator` (UID 1000)
2. **Secret Management**: Credentials stored in Kubernetes secrets
3. **RBAC**: Minimal permissions (only ModalDeployments CRD access)
4. **Network Policies**: Can be restricted to necessary endpoints
5. **Read-only Filesystem**: Could be enabled (Modal CLI writes to ~/.modal)

## Failure Handling

| Scenario           | Behavior                             | Recovery                                      |
| ------------------ | ------------------------------------ | --------------------------------------------- |
| Git clone fails    | Mark as Failed, update status        | User fixes repo/credentials, operator retries |
| Modal deploy fails | Mark as Failed, show error in status | User fixes app code, operator retries         |
| App ID not found   | Warning logged, deletion continues   | Non-blocking - allows resource cleanup        |
| Modal stop fails   | Warning logged, deletion continues   | Non-blocking - prevents stuck deletions       |
| Operator restart   | Retrieves state from CRD status      | App ID persisted, deletion still works        |

## Monitoring Points

```mermaid
graph LR
    A[Health Endpoints] -->|/healthz| B[Liveness Check]
    A -->|/readyz| C[Readiness Check]

    D[Operator Logs] -->|Structured| E[Log Aggregation]

    F[CRD Status] -->|phase, conditions| G[Status Tracking]

    H[Kubernetes Events] -->|Create, Update, Delete| I[Event History]

    style B fill:#C8E6C9
    style C fill:#C8E6C9
    style E fill:#FFF9C4
    style G fill:#E1BEE7
```

### Observable Metrics

- **Health**: `/healthz` (liveness), `/readyz` (readiness) on port 8081
- **Status**: CRD `status.phase` and `status.conditions`
- **Logs**: Structured logging with INFO/WARNING/ERROR levels
- **Events**: Kubernetes events for major lifecycle changes

## Performance Characteristics

| Operation        | Time   | Notes                   |
| ---------------- | ------ | ----------------------- |
| Git Clone        | 1-5s   | Depends on repo size    |
| Modal Deploy     | 5-30s  | Depends on dependencies |
| App ID Query     | 1-2s   | Single API call         |
| Total Deployment | 10-40s | End-to-end              |
| Deletion         | 1-3s   | With cached app ID      |

## Future Enhancements

- [ ] **Automatic git polling and reconciliation** - [Issue #5](https://github.com/mishraprafful/gitops-modal/issues/5)
  - Watch for git commit changes
  - Configurable polling interval
  - Track git revision in CRD status
- [ ] Prometheus metrics exposure - [Issue #7](https://github.com/mishraprafful/gitops-modal/issues/7)
- [ ] Webhook validation for CRDs - [Issue #8](https://github.com/mishraprafful/gitops-modal/issues/8)
