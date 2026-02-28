# Design Document — ugsys-projects-registry

## Overview

`ugsys-projects-registry` is Phase 2 of the ugsys platform. It extracts the project catalog and volunteer subscription management from the Registry monolith into a standalone Python microservice following the same hexagonal architecture as `ugsys-identity-manager` and `ugsys-user-profile-service`.

The service owns three bounded contexts:
- **Project catalog** — CRUD, publish/unpublish, status lifecycle (`pending → active → completed | cancelled`)
- **Volunteer subscriptions** — apply, approve, reject, cancel with dynamic form data
- **Dynamic forms** — per-project custom fields (up to 20) with validation

It is serverless (Lambda + API Gateway via Mangum), uses DynamoDB for persistence across three tables, publishes domain events to EventBridge, consumes `identity.user.deactivated` events, and integrates with `ugsys-identity-manager` via S2S tokens for public registration flows.

### Key Design Decisions

- **ULIDs over UUIDs** — lexicographically sortable, time-ordered, used for all entity IDs
- **Three DynamoDB tables** — projects, subscriptions, form-submissions — each with purpose-built GSIs
- **Participant count as a derived invariant** — `project.current_participants` is maintained in sync with active subscription count via atomic conditional updates
- **S2S token caching** — the service caches its service token (TTL-based) to avoid re-fetching on every public request
- **Event-first design** — every state transition publishes a domain event; event failures are logged but do not roll back the primary operation
- **FormSchema stored on Project** — the schema is a JSON attribute on the Project DynamoDB item (not a separate table), capped at 50KB


## Architecture

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              AWS Cloud                                          │
│                                                                                 │
│  ┌──────────────┐    ┌──────────────────────────────────────────────────────┐  │
│  │   CloudFront  │    │                  API Gateway                         │  │
│  │  (CDN images) │    │  https://api.cbba.cloud.org.bo/projects-registry/   │  │
│  │  cdn.cbba...  │    └──────────────────────┬───────────────────────────────┘  │
│  └──────┬────────┘                           │ HTTP                             │
│         │                          ┌─────────▼──────────────────────────────┐  │
│  ┌──────▼────────┐                 │           Lambda Function               │  │
│  │   S3 Bucket   │                 │   ugsys-projects-registry-{env}         │  │
│  │ ugsys-images  │◄────presigned   │                                         │  │
│  │    -{env}     │     upload      │  ┌──────────────────────────────────┐   │  │
│  └───────────────┘                 │  │  Mangum (ASGI adapter)           │   │  │
│                                    │  │  FastAPI app (create_app())      │   │  │
│                                    │  │  ├── CorrelationIdMiddleware      │   │  │
│                                    │  │  ├── SecurityHeadersMiddleware    │   │  │
│                                    │  │  ├── RateLimitMiddleware          │   │  │
│                                    │  │  └── Routers (v1)                 │   │  │
│                                    │  │      ├── projects.py              │   │  │
│                                    │  │      ├── subscriptions.py         │   │  │
│                                    │  │      ├── public.py                │   │  │
│                                    │  │      ├── form_submissions.py      │   │  │
│                                    │  │      ├── images.py                │   │  │
│                                    │  │      ├── admin.py                 │   │  │
│                                    │  │      └── health.py                │   │  │
│                                    │  └──────────────────────────────────┘   │  │
│                                    └──────────────────────────────────────────┘  │
│                                         │              │              │           │
│                              ┌──────────▼──┐  ┌────────▼──────┐  ┌──▼────────┐  │
│                              │  DynamoDB   │  │  EventBridge  │  │ Identity  │  │
│                              │  Tables:    │  │  ugsys-       │  │ Manager   │  │
│                              │  projects   │  │  platform-bus │  │ (S2S JWT) │  │
│                              │  subscript. │  │               │  │           │  │
│                              │  form-sub.  │  │  ◄── consume  │  └───────────┘  │
│                              └─────────────┘  │  identity.    │                 │
│                                               │  user.deact.  │                 │
│                                               └───────────────┘                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Layer Structure (Hexagonal Architecture)

```
src/
├── presentation/
│   ├── api/v1/
│   │   ├── projects.py
│   │   ├── subscriptions.py
│   │   ├── public.py
│   │   ├── form_submissions.py
│   │   ├── images.py
│   │   ├── admin.py
│   │   └── health.py
│   └── middleware/
│       ├── correlation_id.py
│       ├── security_headers.py
│       └── rate_limiting.py
├── application/
│   ├── services/
│   │   ├── project_service.py
│   │   ├── subscription_service.py
│   │   ├── form_service.py
│   │   ├── public_service.py
│   │   ├── admin_service.py
│   │   ├── image_service.py
│   │   └── event_consumer_service.py
│   ├── commands/
│   ├── queries/
│   │   └── project_queries.py
│   └── dtos/
├── domain/
│   ├── entities/
│   │   ├── project.py
│   │   ├── subscription.py
│   │   ├── form_schema.py
│   │   └── form_submission.py
│   ├── value_objects/
│   │   └── project_status.py
│   ├── repositories/
│   │   ├── project_repository.py
│   │   ├── subscription_repository.py
│   │   ├── form_submission_repository.py
│   │   ├── event_publisher.py
│   │   ├── identity_client.py
│   │   └── circuit_breaker.py
│   └── exceptions.py
└── infrastructure/
    ├── persistence/
    │   ├── dynamodb_project_repository.py
    │   ├── dynamodb_subscription_repository.py
    │   └── dynamodb_form_submission_repository.py
    ├── adapters/
    │   ├── identity_manager_client.py
    │   ├── in_memory_circuit_breaker.py
    │   └── s2s_token_provider.py
    ├── messaging/
    │   └── event_publisher.py
    └── logging.py
```


## Components and Interfaces

### Domain Layer — Entities

#### `Project` (`src/domain/entities/project.py`)

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from src.domain.value_objects.project_status import ProjectStatus

@dataclass
class Project:
    # Identity
    id: str                          # ULID
    name: str                        # max 200 chars
    description: str                 # max 5000 chars
    rich_text: str = ""              # max 10000 chars
    category: str = ""
    # Lifecycle
    status: ProjectStatus = ProjectStatus.PENDING
    is_enabled: bool = False
    # Participants
    max_participants: int = 0        # >= 1
    current_participants: int = 0
    # Dates
    start_date: str = ""             # ISO 8601
    end_date: str = ""               # ISO 8601, must be >= start_date
    # Ownership
    created_by: str = ""             # person_id (ULID)
    # Notifications
    notification_emails: list[str] = field(default_factory=list)
    enable_subscription_notifications: bool = False
    # Images
    images: list[ProjectImage] = field(default_factory=list)
    # Form
    form_schema: FormSchema | None = None
    # Timestamps
    created_at: str = ""             # ISO 8601
    updated_at: str = ""             # ISO 8601
    # Migration
    migrated_from: str | None = None
    migrated_at: str | None = None
```

#### `Subscription` (`src/domain/entities/subscription.py`)

```python
@dataclass
class Subscription:
    id: str                          # ULID
    project_id: str                  # ULID
    person_id: str                   # ULID (from JWT sub)
    status: SubscriptionStatus = SubscriptionStatus.PENDING
    notes: str = ""                  # max 1000 chars
    subscription_date: str = ""      # ISO 8601
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""
    # Migration
    migrated_from: str | None = None
    migrated_at: str | None = None
```

#### `FormSchema` / `CustomField` (`src/domain/entities/form_schema.py`)

```python
from enum import StrEnum

class FieldType(StrEnum):
    TEXT = "text"
    TEXTAREA = "textarea"
    POLL_SINGLE = "poll_single"
    POLL_MULTIPLE = "poll_multiple"
    DATE = "date"
    NUMBER = "number"

@dataclass
class CustomField:
    id: str                          # unique within schema
    field_type: FieldType
    question: str                    # max 500 chars
    required: bool = False
    options: list[str] = field(default_factory=list)  # 2-10 for poll types

@dataclass
class FormSchema:
    fields: list[CustomField] = field(default_factory=list)  # max 20
```

#### `FormSubmission` (`src/domain/entities/form_submission.py`)

```python
@dataclass
class FormSubmission:
    id: str                          # ULID
    project_id: str
    person_id: str
    responses: dict[str, Any]        # field_id -> response value
    created_at: str = ""
    updated_at: str = ""
    migrated_from: str | None = None
    migrated_at: str | None = None
```

#### `ProjectImage` (`src/domain/entities/project.py`)

```python
@dataclass
class ProjectImage:
    image_id: str                    # ULID
    filename: str
    content_type: str
    cloudfront_url: str
    uploaded_at: str
```

#### `ProjectStatus` / `SubscriptionStatus` (`src/domain/value_objects/project_status.py`)

```python
class ProjectStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class SubscriptionStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
```

### Domain Layer — Repository ABCs

#### `ProjectRepository` (`src/domain/repositories/project_repository.py`)

```python
class ProjectRepository(ABC):
    @abstractmethod
    async def save(self, project: Project) -> Project: ...
    @abstractmethod
    async def find_by_id(self, project_id: str) -> Project | None: ...
    @abstractmethod
    async def update(self, project: Project) -> Project: ...
    @abstractmethod
    async def delete(self, project_id: str) -> None: ...
    @abstractmethod
    async def list_paginated(
        self, page: int, page_size: int,
        status_filter: str | None = None,
        category_filter: str | None = None,
    ) -> tuple[list[Project], int]: ...
    @abstractmethod
    async def list_public(self, limit: int) -> list[Project]: ...
    # Returns only status=active AND is_enabled=true, excludes notification_emails
    @abstractmethod
    async def list_by_query(self, query: "ProjectListQuery") -> tuple[list[Project], int]:
        """List projects matching the query criteria with total count."""
        ...
```

#### `SubscriptionRepository` (`src/domain/repositories/subscription_repository.py`)

```python
class SubscriptionRepository(ABC):
    @abstractmethod
    async def save(self, subscription: Subscription) -> Subscription: ...
    @abstractmethod
    async def find_by_id(self, subscription_id: str) -> Subscription | None: ...
    @abstractmethod
    async def update(self, subscription: Subscription) -> Subscription: ...
    @abstractmethod
    async def find_by_person_and_project(
        self, person_id: str, project_id: str
    ) -> Subscription | None: ...
    @abstractmethod
    async def list_by_project(
        self, project_id: str, page: int, page_size: int
    ) -> tuple[list[Subscription], int]: ...
    @abstractmethod
    async def list_by_person(self, person_id: str) -> list[Subscription]: ...
    @abstractmethod
    async def cancel_all_for_person(self, person_id: str) -> int: ...
    # Returns count of cancelled subscriptions
```

#### `FormSubmissionRepository` (`src/domain/repositories/form_submission_repository.py`)

```python
class FormSubmissionRepository(ABC):
    @abstractmethod
    async def save(self, submission: FormSubmission) -> FormSubmission: ...
    @abstractmethod
    async def find_by_person_and_project(
        self, person_id: str, project_id: str
    ) -> FormSubmission | None: ...
    @abstractmethod
    async def list_by_project(self, project_id: str) -> list[FormSubmission]: ...
```

#### `EventPublisher` (`src/domain/repositories/event_publisher.py`)

```python
class EventPublisher(ABC):
    @abstractmethod
    async def publish(self, detail_type: str, payload: dict[str, Any]) -> None: ...
```

#### `IdentityClient` (`src/domain/repositories/identity_client.py`)

```python
class IdentityClient(ABC):
    @abstractmethod
    async def check_email_exists(self, email: str) -> bool: ...
    @abstractmethod
    async def create_user(
        self, email: str, full_name: str, password: str
    ) -> str: ...  # returns user_id
    @abstractmethod
    async def register_service(
        self,
        service_id: str,
        display_name: str,
        version: str,
        nav_icon: str,
        health_url: str,
        config_schema: dict[str, Any],
        roles: list[dict[str, str]],
    ) -> None: ...
    @abstractmethod
    async def get_service_config(self, service_id: str) -> dict[str, Any]: ...
```

#### `CircuitBreaker` (`src/domain/repositories/circuit_breaker.py`)

```python
from abc import ABC, abstractmethod
from enum import StrEnum

class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker(ABC):
    @abstractmethod
    def state(self) -> CircuitState: ...

    @abstractmethod
    def record_success(self) -> None: ...

    @abstractmethod
    def record_failure(self) -> None: ...

    @abstractmethod
    def allow_request(self) -> bool: ...
```


### Infrastructure Layer — DynamoDB Implementations

#### `DynamoDBProjectRepository` (`src/infrastructure/persistence/dynamodb_project_repository.py`)

Implements `ProjectRepository`. Follows repository-pattern.md exactly.

```python
class DynamoDBProjectRepository(ProjectRepository):
    def __init__(self, table_name: str, client: Any) -> None:
        self._table_name = table_name
        self._client = client

    async def save(self, project: Project) -> Project:
        try:
            await self._client.put_item(
                TableName=self._table_name,
                Item=self._to_item(project),
                ConditionExpression="attribute_not_exists(PK)",
            )
            return project
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise RepositoryError(
                    message=f"Project {project.id} already exists",
                    user_message="An unexpected error occurred",
                    error_code="REPOSITORY_ERROR",
                )
            self._raise_repository_error("save", e)

    def _to_item(self, project: Project) -> dict[str, Any]:
        item: dict[str, Any] = {
            "PK": {"S": f"PROJECT#{project.id}"},
            "SK": {"S": "PROJECT"},
            "id": {"S": project.id},
            "name": {"S": project.name},
            "description": {"S": project.description},
            "status": {"S": project.status.value},
            "is_enabled": {"BOOL": project.is_enabled},
            "max_participants": {"N": str(project.max_participants)},
            "current_participants": {"N": str(project.current_participants)},
            "created_by": {"S": project.created_by},
            "created_at": {"S": project.created_at},
            "updated_at": {"S": project.updated_at},
            # GSI attributes
            "status_created_at": {"S": f"{project.status.value}#{project.created_at}"},
        }
        # Optional fields — only write if non-empty/non-None
        if project.rich_text:
            item["rich_text"] = {"S": project.rich_text}
        if project.category:
            item["category"] = {"S": project.category}
        if project.start_date:
            item["start_date"] = {"S": project.start_date}
        if project.end_date:
            item["end_date"] = {"S": project.end_date}
        if project.notification_emails:
            item["notification_emails"] = {"SS": project.notification_emails}
        if project.enable_subscription_notifications:
            item["enable_subscription_notifications"] = {"BOOL": True}
        if project.images:
            item["images"] = {"S": json.dumps([asdict(img) for img in project.images])}
        if project.form_schema is not None:
            item["form_schema"] = {"S": json.dumps(asdict(project.form_schema))}
        if project.migrated_from:
            item["migrated_from"] = {"S": project.migrated_from}
        if project.migrated_at:
            item["migrated_at"] = {"S": project.migrated_at}
        return item

    def _from_item(self, item: dict[str, Any]) -> Project:
        form_schema_raw = item.get("form_schema", {}).get("S")
        form_schema = _deserialize_form_schema(json.loads(form_schema_raw)) if form_schema_raw else None
        images_raw = item.get("images", {}).get("S")
        images = [ProjectImage(**img) for img in json.loads(images_raw)] if images_raw else []
        return Project(
            id=item["id"]["S"],
            name=item["name"]["S"],
            description=item["description"]["S"],
            rich_text=item.get("rich_text", {}).get("S", ""),
            category=item.get("category", {}).get("S", ""),
            status=ProjectStatus(item["status"]["S"]),
            is_enabled=item.get("is_enabled", {}).get("BOOL", False),
            max_participants=int(item["max_participants"]["N"]),
            current_participants=int(item.get("current_participants", {"N": "0"})["N"]),
            start_date=item.get("start_date", {}).get("S", ""),
            end_date=item.get("end_date", {}).get("S", ""),
            created_by=item["created_by"]["S"],
            notification_emails=list(item.get("notification_emails", {}).get("SS", [])),
            enable_subscription_notifications=item.get(
                "enable_subscription_notifications", {}
            ).get("BOOL", False),
            images=images,
            form_schema=form_schema,
            created_at=item["created_at"]["S"],
            updated_at=item["updated_at"]["S"],
            migrated_from=item.get("migrated_from", {}).get("S"),
            migrated_at=item.get("migrated_at", {}).get("S"),
        )

    def _raise_repository_error(self, operation: str, e: ClientError) -> None:
        logger.error(
            "dynamodb.error",
            operation=operation,
            table=self._table_name,
            error_code=e.response["Error"]["Code"],
            error=str(e),
        )
        raise RepositoryError(
            message=f"DynamoDB {operation} failed on {self._table_name}: {e}",
            user_message="An unexpected error occurred",
            error_code="REPOSITORY_ERROR",
        )
```

`DynamoDBSubscriptionRepository` and `DynamoDBFormSubmissionRepository` follow the identical pattern with their respective `_to_item`/`_from_item` implementations.

#### `EventBridgePublisher` (`src/infrastructure/messaging/event_publisher.py`)

```python
class EventBridgePublisher(EventPublisher):
    def __init__(self, event_bus_name: str, client: Any) -> None:
        self._bus = event_bus_name
        self._client = client

    async def publish(self, detail_type: str, payload: dict[str, Any]) -> None:
        try:
            envelope = {
                "event_id": str(uuid4()),
                "event_version": "1.0",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "correlation_id": correlation_id_var.get(""),
                "payload": payload,
            }
            await self._client.put_events(Entries=[{
                "Source": "ugsys.projects-registry",
                "DetailType": detail_type,
                "Detail": json.dumps(envelope),
                "EventBusName": self._bus,
            }])
        except ClientError as e:
            logger.error(
                "eventbridge.publish_failed",
                detail_type=detail_type,
                error=str(e),
            )
            raise ExternalServiceError(
                message=f"EventBridge publish failed: {e}",
                user_message="An unexpected error occurred",
                error_code="EVENT_PUBLISH_FAILED",
            )
```

#### `IdentityManagerClient` (`src/infrastructure/adapters/identity_manager_client.py`)

```python
class IdentityManagerClient(IdentityClient):
    def __init__(
        self, base_url: str, s2s_token_provider: S2STokenProvider, circuit_breaker: CircuitBreaker
    ) -> None:
        self._base_url = base_url
        self._token_provider = s2s_token_provider
        self._cb = circuit_breaker

    async def _call_with_circuit_breaker(
        self, operation: str, coro_factory: Any
    ) -> Any:
        """Wrap an HTTP call with circuit breaker logic."""
        if not self._cb.allow_request():
            logger.warning("identity_client.circuit_open", operation=operation)
            raise ExternalServiceError(
                message=f"Identity Manager circuit breaker is open for {operation}",
                user_message="Service temporarily unavailable, please try again later",
                error_code="SERVICE_UNAVAILABLE",
            )
        try:
            result = await coro_factory()
            self._cb.record_success()
            return result
        except ExternalServiceError:
            self._cb.record_failure()
            raise
        except Exception as e:
            self._cb.record_failure()
            raise ExternalServiceError(
                message=f"Identity Manager {operation} failed: {e}",
                user_message="Service temporarily unavailable, please try again later",
                error_code="EXTERNAL_SERVICE_ERROR",
            )

    async def check_email_exists(self, email: str) -> bool:
        async def _call() -> bool:
            token = await self._token_provider.get_token()
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/api/v1/auth/check-email",
                    json={"email": email},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5.0,
                )
            if resp.status_code == 200:
                return resp.json().get("exists", False)
            raise ExternalServiceError(
                message=f"Identity Manager check-email failed: {resp.status_code}",
                user_message="An unexpected error occurred",
                error_code="IDENTITY_SERVICE_ERROR",
            )
        return await self._call_with_circuit_breaker("check_email_exists", _call)

    async def create_user(self, email: str, full_name: str, password: str) -> str:
        async def _call() -> str:
            token = await self._token_provider.get_token()
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/api/v1/users",
                    json={"email": email, "full_name": full_name, "password": password},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5.0,
                )
            if resp.status_code == 201:
                return resp.json()["data"]["id"]
            raise ExternalServiceError(
                message=f"Identity Manager create-user failed: {resp.status_code}",
                user_message="An unexpected error occurred",
                error_code="IDENTITY_SERVICE_ERROR",
            )
        return await self._call_with_circuit_breaker("create_user", _call)

    async def register_service(
        self,
        service_id: str,
        display_name: str,
        version: str,
        nav_icon: str,
        health_url: str,
        config_schema: dict[str, Any],
        roles: list[dict[str, str]],
    ) -> None:
        async def _call() -> None:
            token = await self._token_provider.get_token()
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/api/v1/services/register",
                    json={
                        "service_id": service_id,
                        "display_name": display_name,
                        "version": version,
                        "nav_icon": nav_icon,
                        "health_url": health_url,
                        "roles": roles,
                        "config_schema": config_schema,
                    },
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0,
                )
            if resp.status_code == 200:
                return
            raise ExternalServiceError(
                message=f"Identity Manager register-service failed: {resp.status_code}",
                user_message="Service registration failed",
                error_code="IDENTITY_SERVICE_ERROR",
            )
        await self._call_with_circuit_breaker("register_service", _call)

    async def get_service_config(self, service_id: str) -> dict[str, Any]:
        async def _call() -> dict[str, Any]:
            token = await self._token_provider.get_token()
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._base_url}/api/v1/services/{service_id}/config",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5.0,
                )
            if resp.status_code == 200:
                return resp.json().get("config", {})
            raise ExternalServiceError(
                message=f"Identity Manager get-service-config failed: {resp.status_code}",
                user_message="An unexpected error occurred",
                error_code="IDENTITY_SERVICE_ERROR",
            )
        return await self._call_with_circuit_breaker("get_service_config", _call)
```

#### `S2STokenProvider` (`src/infrastructure/adapters/s2s_token_provider.py`)

Caches the service token in memory with TTL-based refresh. On startup, the service fetches a token via `client_credentials` grant from Identity Manager. The token is cached until 60 seconds before expiry.

```python
class S2STokenProvider:
    def __init__(self, token_url: str, client_id: str, client_secret: str) -> None:
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._cached_token: str | None = None
        self._expires_at: float = 0.0

    async def get_token(self) -> str:
        if self._cached_token and time.time() < self._expires_at - 60:
            return self._cached_token
        return await self._refresh_token()

    async def _refresh_token(self) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self._token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                timeout=5.0,
            )
        resp.raise_for_status()
        data = resp.json()
        self._cached_token = data["access_token"]
        self._expires_at = time.time() + data["expires_in"]
        return self._cached_token
```

#### `InMemoryCircuitBreaker` (`src/infrastructure/adapters/in_memory_circuit_breaker.py`)

```python
import time
import structlog
from src.domain.repositories.circuit_breaker import CircuitBreaker, CircuitState

logger = structlog.get_logger()

class InMemoryCircuitBreaker(CircuitBreaker):
    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        cooldown_seconds: int = 30,
    ) -> None:
        self._service_name = service_name
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0

    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self._cooldown_seconds:
                self._state = CircuitState.HALF_OPEN
                logger.info("circuit_breaker.half_open", service=self._service_name)
        return self._state

    def allow_request(self) -> bool:
        current = self.state()
        return current in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def record_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            logger.info("circuit_breaker.closed", service=self._service_name)
        self._state = CircuitState.CLOSED
        self._failure_count = 0

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "circuit_breaker.opened",
                service=self._service_name,
                failure_count=self._failure_count,
                cooldown_seconds=self._cooldown_seconds,
            )
```


### Application Layer — Services

#### `ProjectService` (`src/application/services/project_service.py`)

Orchestrates project CRUD, publish/unpublish, and status lifecycle.

Key methods:
- `create(cmd: CreateProjectCommand, requester_id: str) -> Project` — validates date range and max_participants, generates ULID, sets status=pending, publishes `projects.project.created`
- `get(project_id: str, requester_id: str, is_admin: bool) -> Project` — raises `NotFoundError` if not found
- `list_all(query: ListProjectsQuery) -> tuple[list[Project], int]` — admin only, paginated
- `list_public(limit: int) -> list[Project]` — no auth, filters active+enabled, strips notification_emails
- `update(cmd: UpdateProjectCommand, requester_id: str, is_admin: bool) -> Project` — IDOR check (owner or admin), publishes `projects.project.updated`; if status→active publishes `projects.project.published`; if status→completed/cancelled cascades to subscriptions
- `delete(project_id: str, requester_id: str, is_admin: bool) -> None` — admin only, publishes `projects.project.deleted`

#### `ProjectListQuery` (`src/application/queries/project_queries.py`)

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ProjectListQuery:
    """Encapsulates all filter/sort/pagination criteria for project listing."""
    page: int = 1
    page_size: int = 20
    status: str | None = None
    category: str | None = None
    owner_id: str | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"

    def has_filters(self) -> bool:
        return any([self.status, self.category, self.owner_id])
```

#### `SubscriptionService` (`src/application/services/subscription_service.py`)

Key methods:
- `subscribe(cmd: CreateSubscriptionCommand, requester_id: str, is_super_admin: bool) -> Subscription` — duplicate check via `find_by_person_and_project`, generates ULID, status=active if super_admin else pending, increments `current_participants` if active, publishes `projects.subscription.created`
- `approve(cmd: ApproveSubscriptionCommand, requester_id: str) -> Subscription` — admin only, status→active, increments count, publishes `projects.subscription.approved`
- `reject(cmd: RejectSubscriptionCommand, requester_id: str) -> Subscription` — admin only, status→rejected, publishes `projects.subscription.rejected`
- `cancel(subscription_id: str, project_id: str, requester_id: str, is_admin: bool) -> None` — owner or admin, decrements count if was active, publishes `projects.subscription.cancelled`
- `list_by_project(project_id: str, page: int, page_size: int) -> tuple[list[Subscription], int]`
- `list_by_person(person_id: str, requester_id: str, is_admin: bool) -> list[EnrichedSubscription]` — IDOR check, enriches with project fields

#### `FormService` (`src/application/services/form_service.py`)

Key methods:
- `update_schema(project_id: str, schema: FormSchema, requester_id: str, is_admin: bool) -> Project` — validates field count ≤20, no duplicate IDs, poll options 2-10, serialized size ≤50KB
- `submit(cmd: SubmitFormCommand, requester_id: str) -> FormSubmission` — validates responses against schema, stores submission
- `get_submission(person_id: str, project_id: str, requester_id: str, is_admin: bool) -> FormSubmission` — IDOR check
- `list_by_project(project_id: str) -> list[FormSubmission]` — admin only

#### `PublicService` (`src/application/services/public_service.py`)

Handles unauthenticated flows. Uses `IdentityClient` for user operations.

Key methods:
- `check_email(email: str) -> bool`
- `register(cmd: PublicRegisterCommand) -> PublicRegisterResult` — calls `identity_client.check_email_exists`, if not exists calls `identity_client.create_user`
- `subscribe(cmd: PublicSubscribeCommand) -> Subscription` — creates user if needed, then creates subscription with status=pending, publishes event

#### `AdminService` (`src/application/services/admin_service.py`)

Key methods:
- `dashboard() -> DashboardData` — aggregates counts from all three repositories
- `enhanced_dashboard() -> EnhancedDashboardData` — adds per-project stats and recent signups
- `analytics() -> AnalyticsData` — breakdown by status
- `paginated_users(query: PaginatedUsersQuery) -> tuple[list[UserSummary], int]` — delegates to IdentityClient
- `bulk_action(cmd: BulkActionCommand) -> BulkActionResult` — processes each user_id, checks for active/pending subscriptions before delete, returns per-user results

#### `ImageService` (`src/application/services/image_service.py`)

Key methods:
- `generate_upload_url(cmd: GenerateUploadUrlCommand, requester_id: str) -> UploadUrlResult` — validates file_size ≤10MB and content_type, generates ULID image_id, calls S3 presigned URL generation, returns presigned URL + CloudFront URL

#### `EventConsumerService` (`src/application/services/event_consumer_service.py`)

Key methods:
- `handle_user_deactivated(person_id: str) -> None` — calls `subscription_repo.cancel_all_for_person(person_id)`, publishes `projects.subscription.cancelled` for each cancelled subscription, logs count

### Presentation Layer — API Routers

#### Route Map

| Method | Path | Auth | Service |
|--------|------|------|---------|
| POST | /api/v1/projects | JWT | ProjectService.create |
| GET | /api/v1/projects | Admin JWT | ProjectService.list_all |
| GET | /api/v1/projects/public | None | ProjectService.list_public |
| GET | /api/v1/projects/{id} | JWT | ProjectService.get |
| PUT | /api/v1/projects/{id} | JWT | ProjectService.update |
| DELETE | /api/v1/projects/{id} | Admin JWT | ProjectService.delete |
| PUT | /api/v1/projects/{id}/form-schema | JWT | FormService.update_schema |
| GET | /api/v1/projects/{id}/enhanced | JWT | ProjectService.get (with form_schema) |
| POST | /api/v1/projects/enhanced | JWT | ProjectService.create + FormService.update_schema |
| POST | /api/v1/projects/{id}/subscriptions | JWT | SubscriptionService.subscribe |
| GET | /api/v1/projects/{id}/subscriptions | Admin/Mod JWT | SubscriptionService.list_by_project |
| PUT | /api/v1/projects/{id}/subscribers/{sub_id} | Admin JWT | SubscriptionService.approve/reject |
| DELETE | /api/v1/projects/{id}/subscribers/{sub_id} | JWT | SubscriptionService.cancel |
| GET | /api/v1/subscriptions/person/{person_id} | JWT | SubscriptionService.list_by_person |
| POST | /api/v1/subscriptions/check | JWT | SubscriptionService.check |
| POST | /api/v1/form-submissions | JWT | FormService.submit |
| GET | /api/v1/form-submissions/project/{project_id} | Admin JWT | FormService.list_by_project |
| GET | /api/v1/form-submissions/person/{person_id}/project/{project_id} | JWT | FormService.get_submission |
| POST | /api/v1/public/check-email | None | PublicService.check_email |
| POST | /api/v1/public/register | None | PublicService.register |
| POST | /api/v1/public/subscribe | None | PublicService.subscribe |
| POST | /api/v1/images/upload-url | JWT | ImageService.generate_upload_url |
| GET | /api/v1/admin/dashboard | Admin JWT | AdminService.dashboard |
| GET | /api/v1/admin/dashboard/enhanced | Admin JWT | AdminService.enhanced_dashboard |
| GET | /api/v1/admin/analytics | Admin JWT | AdminService.analytics |
| GET | /api/v1/admin/users/paginated | Admin JWT | AdminService.paginated_users |
| POST | /api/v1/admin/users/bulk-action | Admin JWT | AdminService.bulk_action |
| GET | /api/v1/admin/subscriptions | Admin JWT | SubscriptionService.list_all |
| GET | /health | None | — |
| GET | / | None | — |

#### Response Envelope

All successful responses:
```json
{ "data": { ... }, "meta": { "request_id": "..." } }
```

All error responses:
```json
{ "error": "<ERROR_CODE>", "message": "<user_safe_message>", "data": {} }
```

#### EventBridge Consumer Handler (`src/presentation/event_consumer.py`)

Separate Lambda handler entry point for EventBridge events:

```python
async def handle_event(event: dict[str, Any]) -> None:
    detail_type = event.get("detail-type", "")
    detail = event.get("detail", {})
    logger.info("event.received", detail_type=detail_type, source=event.get("source"))

    if detail_type == "identity.user.deactivated":
        person_id = detail.get("payload", {}).get("user_id")
        await event_consumer_service.handle_user_deactivated(person_id)
    else:
        logger.warning("event.unhandled", detail_type=detail_type)
```


## Data Models

### DynamoDB Table Schemas

#### Projects Table — `ugsys-projects-{env}`

| Attribute | Type | Notes |
|-----------|------|-------|
| PK | S | `PROJECT#{id}` |
| SK | S | `PROJECT` |
| id | S | ULID |
| name | S | max 200 chars, html.escape'd |
| description | S | max 5000 chars, html.escape'd |
| rich_text | S | max 10000 chars, optional |
| category | S | optional |
| status | S | pending \| active \| completed \| cancelled |
| is_enabled | BOOL | |
| max_participants | N | |
| current_participants | N | maintained in sync with active subscriptions |
| start_date | S | ISO 8601 |
| end_date | S | ISO 8601 |
| created_by | S | person_id ULID |
| notification_emails | SS | string set, optional |
| enable_subscription_notifications | BOOL | optional |
| images | S | JSON array of ProjectImage |
| form_schema | S | JSON, max 50KB |
| created_at | S | ISO 8601 |
| updated_at | S | ISO 8601 |
| status_created_at | S | `{status}#{created_at}` — GSI-1 SK |
| migrated_from | S | optional |
| migrated_at | S | optional |

GSI-1: `status-index` — PK=`status`, SK=`status_created_at` (for filtered listing by status)
GSI-2: `created_by-index` — PK=`created_by` (for listing projects by owner)

#### Subscriptions Table — `ugsys-subscriptions-{env}`

| Attribute | Type | Notes |
|-----------|------|-------|
| PK | S | `SUB#{id}` |
| SK | S | `SUB` |
| id | S | ULID |
| project_id | S | ULID |
| person_id | S | ULID |
| status | S | pending \| active \| rejected \| cancelled |
| notes | S | max 1000 chars, optional |
| subscription_date | S | ISO 8601 |
| is_active | BOOL | |
| created_at | S | ISO 8601 |
| updated_at | S | ISO 8601 |
| person_project_key | S | `{person_id}#{project_id}` — GSI-3 PK |
| migrated_from | S | optional |
| migrated_at | S | optional |

GSI-1: `person-index` — PK=`person_id`, SK=`created_at`
GSI-2: `project-index` — PK=`project_id`, SK=`created_at`
GSI-3: `person-project-index` — PK=`person_project_key` (duplicate detection — query returns at most one non-cancelled item)

#### Form Submissions Table — `ugsys-form-submissions-{env}`

| Attribute | Type | Notes |
|-----------|------|-------|
| PK | S | `SUBMISSION#{id}` |
| SK | S | `SUBMISSION` |
| id | S | ULID |
| project_id | S | ULID |
| person_id | S | ULID |
| responses | S | JSON dict of field_id → response |
| created_at | S | ISO 8601 |
| updated_at | S | ISO 8601 |
| migrated_from | S | optional |
| migrated_at | S | optional |

GSI-1: `project-index` — PK=`project_id`
GSI-2: `person-index` — PK=`person_id`

### Event Payloads

All events use the `ugsys-event-lib` envelope with source `ugsys.projects-registry` on bus `ugsys-platform-bus`.

| Event | Key Payload Fields |
|-------|-------------------|
| `projects.project.created` | `project_id`, `name`, `status`, `created_by` |
| `projects.project.updated` | `project_id`, `name`, `status`, `updated_by` |
| `projects.project.published` | `project_id`, `name`, `created_by` |
| `projects.project.deleted` | `project_id`, `deleted_by` |
| `projects.subscription.created` | `subscription_id`, `project_id`, `person_id`, `status`, `notification_emails` |
| `projects.subscription.approved` | `subscription_id`, `project_id`, `person_id` |
| `projects.subscription.rejected` | `subscription_id`, `project_id`, `person_id` |
| `projects.subscription.cancelled` | `subscription_id`, `project_id`, `person_id` |

Consumed: `identity.user.deactivated` — payload contains `user_id`, `email`

### `src/config.py`

```python
from typing import Any
from pydantic_settings import BaseSettings

# ── Service Registration Constants (Section 14.2 of platform-contract) ────────

SERVICE_CONFIG_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "max_subscriptions_per_project": {
            "type": "integer",
            "default": 100,
            "description": "Maximum subscriptions allowed per project",
        },
        "admin_notification_email": {
            "type": "string",
            "format": "email",
            "description": "Email address for admin notifications",
        },
        "subscription_approval_required": {
            "type": "boolean",
            "default": False,
            "description": "Require manual approval for subscriptions",
        },
    },
}

SERVICE_ROLES: list[dict[str, str]] = [
    {"name": "projects:admin", "description": "Full projects management"},
    {"name": "projects:viewer", "description": "Read-only access to projects"},
]


class Settings(BaseSettings):
    service_name: str = "ugsys-projects-registry"
    service_id: str = "ugsys-projects-registry"
    display_name: str = "Projects Registry"
    version: str = "1.0.0"
    nav_icon: str = "folder"
    public_base_url: str = "https://api.cbba.cloud.org.bo/projects"
    environment: str = "dev"
    aws_region: str = "us-east-1"
    dynamodb_table_prefix: str = "ugsys"
    event_bus_name: str = "ugsys-platform-bus"
    log_level: str = "INFO"
    # S3
    images_bucket_name: str = ""
    cloudfront_domain: str = "cdn.cbba.cloud.org.bo"
    # Identity Manager
    identity_manager_url: str = ""
    s2s_client_id: str = ""
    s2s_client_secret: str = ""
    s2s_token_url: str = ""
    # JWT validation (via ugsys-auth-client)
    # IMPORTANT: ugsys-auth-client MUST be configured with algorithms=["RS256"] only.
    # HS256 and "none" algorithm tokens are rejected before signature verification (REQ 12.5).
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_region: str = "us-east-1"
    # Operator-configurable defaults (overridden by identity-manager config at startup)
    max_subscriptions_per_project: int = 100
    admin_notification_email: str = ""
    subscription_approval_required: bool = False
    # CORS — explicit allowlist, never wildcard (security.md)
    allowed_origins: list[str] = ["https://admin.cbba.cloud.org.bo", "https://cbba.cloud.org.bo"]

    @property
    def projects_table(self) -> str:
        return f"{self.dynamodb_table_prefix}-projects-{self.environment}"

    @property
    def subscriptions_table(self) -> str:
        return f"{self.dynamodb_table_prefix}-subscriptions-{self.environment}"

    @property
    def form_submissions_table(self) -> str:
        return f"{self.dynamodb_table_prefix}-form-submissions-{self.environment}"

    @property
    def images_bucket(self) -> str:
        return self.images_bucket_name or f"ugsys-images-{self.environment}"

    def apply_remote_config(self, config: dict[str, Any]) -> None:
        """Apply operator-set config values from identity-manager over env var defaults.

        Only known keys are applied; unknown keys are ignored.
        """
        known_keys = {"max_subscriptions_per_project", "admin_notification_email", "subscription_approval_required"}
        for key, value in config.items():
            if key in known_keys and value is not None:
                setattr(self, key, value)

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

### `src/main.py` — Composition Root

```python
configure_logging(settings.service_name, settings.log_level)
logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("startup.begin", service=settings.service_name, version=settings.version)
    session = aioboto3.Session()
    async with (
        session.client("dynamodb", region_name=settings.aws_region) as dynamodb,
        session.client("events", region_name=settings.aws_region) as eventbridge,
        session.client("s3", region_name=settings.aws_region) as s3,
    ):
        # Repositories
        project_repo = DynamoDBProjectRepository(settings.projects_table, dynamodb)
        subscription_repo = DynamoDBSubscriptionRepository(settings.subscriptions_table, dynamodb)
        form_submission_repo = DynamoDBFormSubmissionRepository(settings.form_submissions_table, dynamodb)
        event_publisher = EventBridgePublisher(settings.event_bus_name, eventbridge)
        s2s_provider = S2STokenProvider(
            settings.s2s_token_url, settings.s2s_client_id, settings.s2s_client_secret
        )
        identity_cb = InMemoryCircuitBreaker(service_name="identity-manager", failure_threshold=5, cooldown_seconds=30)
        identity_client = IdentityManagerClient(settings.identity_manager_url, s2s_provider, identity_cb)

        # Services
        app.state.project_service = ProjectService(project_repo, subscription_repo, event_publisher)
        app.state.subscription_service = SubscriptionService(
            subscription_repo, project_repo, event_publisher
        )
        app.state.form_service = FormService(project_repo, form_submission_repo)
        app.state.public_service = PublicService(identity_client, subscription_repo, project_repo, event_publisher)
        app.state.admin_service = AdminService(project_repo, subscription_repo, identity_client)
        app.state.image_service = ImageService(s3, settings.images_bucket, settings.cloudfront_domain)
        app.state.event_consumer_service = EventConsumerService(subscription_repo, event_publisher)

        # 1. Register with identity-manager (schema + roles + metadata)
        #    Non-fatal: log warning and continue if identity-manager is unreachable
        #    (Section 14.2 / 14.7 of platform-contract)
        try:
            await identity_client.register_service(
                service_id=settings.service_id,
                display_name=settings.display_name,
                version=settings.version,
                nav_icon=settings.nav_icon,
                health_url=f"{settings.public_base_url}/api/v1/health",
                config_schema=SERVICE_CONFIG_SCHEMA,
                roles=SERVICE_ROLES,
            )
            logger.info("service.registered", service=settings.service_id)
        except Exception as e:
            logger.warning("service.registration_failed", service=settings.service_id, error=str(e))

        # 2. Fetch operator config from identity-manager (overrides env defaults)
        #    Non-fatal: if unreachable, service runs with env var defaults
        #    (Section 14.2.2 of platform-contract)
        try:
            config = await identity_client.get_service_config(settings.service_id)
            settings.apply_remote_config(config)
            logger.info("service.config_loaded", service=settings.service_id)
        except Exception as e:
            logger.warning("service.config_load_failed", service=settings.service_id, error=str(e))

        logger.info("startup.complete", service=settings.service_name)
        yield
    logger.info("shutdown.complete", service=settings.service_name)


# from fastapi.middleware.cors import CORSMiddleware  # add to imports in main.py

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.service_name,
        version="1.0.0",
        docs_url="/docs" if settings.environment != "prod" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=60)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,  # explicit allowlist — never wildcard
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
    app.add_exception_handler(DomainError, domain_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(health.router)
    app.include_router(projects.router, prefix="/api/v1")
    app.include_router(subscriptions.router, prefix="/api/v1")
    app.include_router(public.router, prefix="/api/v1")
    app.include_router(form_submissions.router, prefix="/api/v1")
    app.include_router(images.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    return app

app = create_app()
```

### `handler.py` — Lambda Entry Point

```python
# handler.py (at repo root, alongside src/)
from mangum import Mangum
from src.main import app

handler = Mangum(app, lifespan="on")
```

### Data Migration — `scripts/migrate_from_registry.py`

The migration script reads from Registry PostgreSQL and writes to DynamoDB. It is idempotent: before writing any record it checks for an existing item with the same original Registry ID stored in a `registry_original_id` attribute.

```
Algorithm:
1. Connect to Registry PostgreSQL (connection string from env var REGISTRY_DB_URL)
2. Connect to DynamoDB (from env vars / IAM role)
3. For each entity type (projects, subscriptions, form_submissions):
   a. SELECT all records from PostgreSQL
   b. For each record:
      - Check DynamoDB for existing item with registry_original_id = record.id
      - If exists: log warning "skipping {id} — already migrated", increment skipped
      - If not exists:
        - Map fields to domain entity (preserve all fields, set migrated_from="registry", migrated_at=now)
        - Map integer id to ULID-formatted string (pad to ULID length)
        - Write to DynamoDB
        - On ClientError: log error, increment failed, continue
        - On success: increment written
4. Log summary: total={N}, written={N}, skipped={N}, failed={N}
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: FormSchema serialization round-trip

*For any* valid `FormSchema` object (any number of fields ≤20, any valid field types, any valid option counts for poll fields), serializing it to JSON and deserializing it back must produce an object equal to the original.

**Validates: Requirements 6.9, 17.5**

### Property 2: Project creation invariants

*For any* valid project creation payload (non-empty name, description, max_participants ≥1, end_date ≥ start_date), the created `Project` must have `status=pending`, `current_participants=0`, and an ID that is a valid ULID string.

**Validates: Requirements 2.1, 1.6**

### Property 3: Date range validation

*For any* project creation payload where `end_date` is strictly before `start_date`, the service must reject the request with error code `INVALID_DATE_RANGE`.

**Validates: Requirements 2.2**

### Property 4: Public endpoint filter invariant

*For any* collection of projects with mixed statuses and `is_enabled` values, the public listing endpoint must return only projects where `status=active` AND `is_enabled=true`, and must never include `notification_emails` in the response.

**Validates: Requirements 2.5, 3.3, 3.4**

### Property 5: Participant count invariant

*For any* project, `current_participants` must always equal the count of subscriptions for that project with `status=active`. This invariant must hold after every subscription creation (auto-approved), approval, cancellation, and project status cascade.

**Validates: Requirements 4.2, 4.4, 4.6, 2.10**

### Property 6: Subscription uniqueness invariant

*For any* `(person_id, project_id)` pair, at most one non-cancelled subscription may exist at any time. Attempting to create a second subscription for the same pair must be rejected with error code `SUBSCRIPTION_ALREADY_EXISTS`.

**Validates: Requirements 4.3, 7.6, 17.6**

### Property 7: Subscription status transition invariant

*For any* subscription, status transitions must follow the valid state machine: `pending → active` (approve), `pending → rejected` (reject), `active → cancelled` (cancel), `pending → cancelled` (cancel). Any other transition (e.g. `rejected → active`, `cancelled → active`) must be rejected.

**Validates: Requirements 4.1, 4.4, 4.5, 4.6**

### Property 8: Project status cascade

*For any* project transitioning to `completed` or `cancelled`, all subscriptions for that project with `status=active` must be updated to match the terminal project status, and `current_participants` must be decremented accordingly.

**Validates: Requirements 2.10, 3.2**

### Property 9: FormSchema validation — field count

*For any* `FormSchema` with more than 20 fields, the service must reject it with error code `FORM_SCHEMA_TOO_MANY_FIELDS`.

**Validates: Requirements 5.2**

### Property 10: FormSchema validation — poll options

*For any* `CustomField` of type `poll_single` or `poll_multiple` with fewer than 2 or more than 10 options, the service must reject the schema with error code `FORM_SCHEMA_INVALID_OPTIONS`.

**Validates: Requirements 5.4**

### Property 11: FormSubmission validation

*For any* form submission, responses for `poll_single` fields must be a string in the field's options list, responses for `poll_multiple` fields must be a list where every item is in the options list, and all fields with `required=true` must have a non-null response. Any violation must be rejected with the appropriate error code.

**Validates: Requirements 6.2, 6.3, 6.4**

### Property 12: FormSubmission round-trip

*For any* valid form submission, submitting it and then retrieving it by `(person_id, project_id)` must return an equivalent `FormSubmission` with all responses preserved.

**Validates: Requirements 6.7**

### Property 13: Public subscription always pending

*For any* request to `POST /api/v1/public/subscribe`, regardless of any claim in the request body, the created subscription must have `status=pending`.

**Validates: Requirements 7.7**

### Property 14: IDOR prevention

*For any* authenticated request where the requester's JWT `sub` does not match the resource owner's `person_id` and the requester does not have an admin role, the service must return HTTP 403 — never HTTP 404 for ownership-protected resources.

**Validates: Requirements 12.2, 12.6**

### Property 15: JWT algorithm rejection

*For any* token signed with an algorithm other than RS256 (including HS256 and `none`), the service must reject it with HTTP 401 before attempting signature verification.

**Validates: Requirements 1.3, 12.5**

### Property 16: Input length validation

*For any* input where `Project.name` exceeds 200 chars, `Project.description` exceeds 5000 chars, `Project.rich_text` exceeds 10000 chars, `Subscription.notes` exceeds 1000 chars, or `CustomField.question` exceeds 500 chars, the service must reject the request with error code `VALIDATION_ERROR`.

**Validates: Requirements 13.3, 13.4, 13.5, 13.6, 13.7**

### Property 17: Security headers invariant

*For any* HTTP response from the service, all required security headers must be present: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`, `Content-Security-Policy`, `Referrer-Policy`, `Permissions-Policy`, and `Cache-Control: no-store` on `/api/*` routes.

**Validates: Requirements 15.7**

### Property 18: Event publishing on state transitions

*For any* project or subscription state transition, the `EventPublisher` must receive exactly one call with the correct `detail_type` matching the transition. Event publish failures must not roll back the primary DynamoDB operation.

**Validates: Requirements 10.1–10.8**

### Property 19: User deactivation cascade

*For any* `identity.user.deactivated` event with a `user_id`, all subscriptions for that user with `status=active` or `status=pending` must be cancelled, and a `projects.subscription.cancelled` event must be published for each one.

**Validates: Requirements 11.1**

### Property 20: Migration idempotency

*For any* Registry record that has already been migrated (identified by `registry_original_id`), running the migration script again must skip that record without overwriting the existing DynamoDB item.

**Validates: Requirements 14.5**

### Property 21: Circuit Breaker state transitions

*For any* sequence of N consecutive failures (N ≥ 5) from `IdentityManagerClient`, the Circuit Breaker must transition to `OPEN` state and reject all subsequent requests immediately with `ExternalServiceError(SERVICE_UNAVAILABLE)` without making HTTP calls. After the cooldown period, it must transition to `HALF_OPEN` and allow exactly one probe request.

**Validates: Requirements 20.1, 20.2, 20.3, 20.4, 20.5, 20.6**

### Property 22: Circuit Breaker fast-fail timing

*For any* request made while the Circuit Breaker is in `OPEN` state, the rejection must occur without any network I/O — the `ExternalServiceError` must be raised before any HTTP client is instantiated or any `await` on network calls occurs.

**Validates: Requirements 20.3**


## Error Handling

### Domain Exception Hierarchy (`src/domain/exceptions.py`)

Identical base hierarchy to `ugsys-identity-manager`:

```python
@dataclass
class DomainError(Exception):
    message: str                          # internal — logs only
    user_message: str = "An error occurred"
    error_code: str = "INTERNAL_ERROR"
    additional_data: dict[str, Any] = field(default_factory=dict)

class ValidationError(DomainError): ...       # 422
class NotFoundError(DomainError): ...         # 404
class ConflictError(DomainError): ...         # 409
class AuthenticationError(DomainError): ...   # 401
class AuthorizationError(DomainError): ...    # 403
class RepositoryError(DomainError): ...       # 500
class ExternalServiceError(DomainError): ...  # 502
```

### Error Code → HTTP Status Mapping

| Error Code | HTTP Status | Raised When |
|------------|-------------|-------------|
| `VALIDATION_ERROR` | 422 | Field length exceeded, invalid input |
| `INVALID_DATE_RANGE` | 422 | end_date < start_date |
| `INVALID_MAX_PARTICIPANTS` | 422 | max_participants < 1 |
| `FORM_SCHEMA_TOO_MANY_FIELDS` | 422 | >20 fields in schema |
| `FORM_SCHEMA_DUPLICATE_FIELD_IDS` | 422 | Duplicate field IDs |
| `FORM_SCHEMA_INVALID_OPTIONS` | 422 | Poll field with <2 or >10 options |
| `FORM_SCHEMA_TOO_LARGE` | 422 | Serialized schema >50KB |
| `FORM_SUBMISSION_INVALID_RESPONSE` | 422 | Invalid poll response |
| `FORM_SUBMISSION_MISSING_REQUIRED_FIELD` | 422 | Required field omitted |
| `PROJECT_HAS_NO_FORM_SCHEMA` | 422 | Submission for project without schema |
| `IMAGE_TOO_LARGE` | 422 | file_size > 10MB |
| `IMAGE_INVALID_CONTENT_TYPE` | 422 | Non-image content type |
| `PROJECT_NOT_FOUND` | 404 | Project ID not found |
| `SUBSCRIPTION_NOT_FOUND` | 404 | Subscription ID not found |
| `FORM_SUBMISSION_NOT_FOUND` | 404 | No submission for person+project |
| `SUBSCRIPTION_ALREADY_EXISTS` | 409 | Duplicate (person_id, project_id) |
| `EMAIL_ALREADY_EXISTS` | 400 | Public register with existing email |
| `FORBIDDEN` | 403 | Non-owner, non-admin access |
| `AUTHENTICATION_FAILED` | 401 | Invalid/missing JWT |
| `BUSINESS_RULE_VIOLATION` | 409 | Bulk delete of user with active subscriptions |
| `REPOSITORY_ERROR` | 500 | DynamoDB ClientError |
| `EXTERNAL_SERVICE_ERROR` | 502 | Identity Manager or EventBridge failure |
| `SERVICE_UNAVAILABLE` | 502 | Circuit Breaker is open — Identity Manager unavailable |

### Exception Handler (`src/presentation/middleware/exception_handler.py`)

```python
STATUS_MAP = {
    ValidationError: 422,
    NotFoundError: 404,
    ConflictError: 409,
    AuthenticationError: 401,
    AuthorizationError: 403,
    RepositoryError: 500,
    ExternalServiceError: 502,
}

async def domain_exception_handler(request: Request, exc: DomainError) -> JSONResponse:
    status = STATUS_MAP.get(type(exc), 500)
    logger.error(
        "domain_error",
        error_code=exc.error_code,
        message=exc.message,   # internal — logs only
        status=status,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=status,
        content={
            "error": exc.error_code,
            "message": exc.user_message,  # safe — never internal detail
            "data": exc.additional_data,
        },
    )
```

### Event Publish Failure Policy

Per Requirement 10.10: if `EventPublisher.publish()` raises, the application service catches the exception, logs at `error` level with `detail_type` and `correlation_id`, and returns normally. The primary DynamoDB write is never rolled back due to an event failure.

```python
try:
    await self._event_publisher.publish("projects.project.created", payload)
except ExternalServiceError as e:
    logger.error(
        "event.publish_failed",
        detail_type="projects.project.created",
        error=str(e),
    )
    # Do not re-raise — primary operation succeeded
```


## Distributed Tracing (AWS X-Ray)

### Instrumentation Approach

Patch boto3/aioboto3 at startup in `src/main.py` using `aws_xray_sdk.core.patch(['boto3'])`. This automatically traces all DynamoDB, EventBridge, and S3 calls without modifying repository or messaging code. The patching is conditional on `settings.xray_tracing_enabled`.

### Startup Patching in `src/main.py`

Before `create_app()`, conditionally patch boto3:

```python
from src.config import settings

if settings.xray_tracing_enabled:
    from aws_xray_sdk.core import patch
    patch(['boto3'])
```

### Configuration

Add to `Settings` in `src/config.py`:

```python
# X-Ray distributed tracing
xray_tracing_enabled: bool = True
xray_sampling_rate: float = 0.05  # 5% of successful requests, 100% of errors
```

### X-Ray Middleware (`src/presentation/middleware/xray_middleware.py`)

A middleware that:
- Reads the incoming `X-Amzn-Trace-Id` header (set by API Gateway)
- Adds `service.name`, `service.version`, `environment` annotations to the segment
- Adds `correlation_id` and `user_id` (if authenticated) as annotations
- Adds request path and method as metadata
- On error responses (4xx/5xx), adds the error code as an annotation

### Service Method Tracing Decorator (`src/infrastructure/tracing.py`)

A decorator `@traced` that:
- Creates an X-Ray subsegment named `{ClassName}.{method_name}`
- Adds `duration_ms` as metadata
- Records exceptions as X-Ray faults
- Falls back to no-op when X-Ray context is not available (tests, local dev)

```python
# src/infrastructure/tracing.py
import functools
import time
import structlog
from contextlib import contextmanager
from typing import Any, Callable

logger = structlog.get_logger()

try:
    from aws_xray_sdk.core import xray_recorder
    XRAY_AVAILABLE = True
except ImportError:
    XRAY_AVAILABLE = False

@contextmanager
def traced_subsegment(name: str) -> Any:
    """Create an X-Ray subsegment if available, no-op otherwise."""
    if not XRAY_AVAILABLE:
        yield None
        return
    try:
        subsegment = xray_recorder.begin_subsegment(name)
        yield subsegment
    except Exception:
        yield None
    finally:
        try:
            xray_recorder.end_subsegment()
        except Exception:
            pass

def traced(func: Callable) -> Callable:
    """Decorator to trace application service methods with X-Ray subsegments."""
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        class_name = args[0].__class__.__name__ if args else ""
        subsegment_name = f"{class_name}.{func.__name__}"
        start = time.perf_counter()
        with traced_subsegment(subsegment_name) as subsegment:
            try:
                result = await func(*args, **kwargs)
                if subsegment:
                    subsegment.put_metadata("duration_ms", round((time.perf_counter() - start) * 1000, 2))
                return result
            except Exception as e:
                if subsegment:
                    subsegment.add_exception(e, stack=True)
                    subsegment.put_metadata("duration_ms", round((time.perf_counter() - start) * 1000, 2))
                raise
    return wrapper
```

### httpx Tracing for Identity Manager

In `IdentityManagerClient`, propagate the `X-Amzn-Trace-Id` header on every outbound request and create a subsegment per outbound call. The `_call_with_circuit_breaker` helper wraps each HTTP call in a `traced_subsegment("IdentityManagerClient.{operation}")` block, and the trace header is read from the current X-Ray segment context (if available) and forwarded as a request header.

### Testing

X-Ray SDK is optional in tests. The `@traced` decorator and middleware fall back to no-op when `aws-xray-sdk` is not importable or when no X-Ray context exists. No mocking of X-Ray is needed in unit tests.

### Property 28: Tracing non-blocking invariant

*For any* request where X-Ray SDK is unavailable or the X-Ray daemon is unreachable, the service must process the request normally without raising exceptions — tracing failures must never affect business logic.

**Validates: Requirements 31.7**


## Testing Strategy

### Dual Testing Approach

Both unit tests and property-based tests are required and complementary:
- **Unit tests** verify specific examples, edge cases, and error conditions
- **Property tests** verify universal properties across many generated inputs

### Test Structure

```
tests/
├── unit/
│   ├── domain/
│   │   ├── test_project.py          # Entity invariants, status transitions
│   │   ├── test_subscription.py     # Status machine, duplicate detection
│   │   ├── test_form_schema.py      # Validation rules, round-trip
│   │   └── test_form_submission.py  # Response validation
│   ├── application/
│   │   ├── test_project_service.py  # CRUD, publish/unpublish, cascade
│   │   ├── test_subscription_service.py  # Subscribe, approve, reject, cancel
│   │   ├── test_form_service.py     # Schema update, submit, retrieve
│   │   ├── test_public_service.py   # check-email, register, subscribe
│   │   ├── test_admin_service.py    # Dashboard, bulk actions
│   │   ├── test_image_service.py    # Presigned URL generation
│   │   └── test_event_consumer_service.py  # User deactivation cascade
│   └── presentation/
│       ├── test_projects_router.py
│       ├── test_subscriptions_router.py
│       ├── test_public_router.py
│       └── test_admin_router.py
└── integration/
    ├── test_dynamodb_project_repository.py
    ├── test_dynamodb_subscription_repository.py
    └── test_dynamodb_form_submission_repository.py
```

### Unit Testing Guidelines

- Mock at the port boundary: `AsyncMock(spec=ProjectRepository)`, `AsyncMock(spec=EventPublisher)`, etc. — never mock `boto3` directly
- Follow AAA (Arrange / Act / Assert) in every test
- Assert domain exception type and `error_code` for error cases
- Assert `user_message` does NOT contain internal details, stack traces, or PII
- Coverage gate: 80% minimum on `src/domain/` and `src/application/`, target 90%+

Example unit test pattern:

```python
async def test_subscribe_raises_conflict_when_duplicate() -> None:
    # Arrange
    sub_repo = AsyncMock(spec=SubscriptionRepository)
    sub_repo.find_by_person_and_project.return_value = make_subscription()
    project_repo = AsyncMock(spec=ProjectRepository)
    project_repo.find_by_id.return_value = make_project()
    event_pub = AsyncMock(spec=EventPublisher)
    service = SubscriptionService(sub_repo, project_repo, event_pub)

    # Act + Assert
    with pytest.raises(ConflictError) as exc_info:
        await service.subscribe(
            CreateSubscriptionCommand(project_id="01J...", person_id="01J..."),
            requester_id="01J...",
            is_super_admin=False,
        )

    assert exc_info.value.error_code == "SUBSCRIPTION_ALREADY_EXISTS"
    assert "01J" not in exc_info.value.user_message  # no IDs in user_message
```

### Property-Based Testing (Hypothesis)

Library: `hypothesis` — do not implement PBT from scratch.
Minimum 100 iterations per property test (Hypothesis default is 100, use `@settings(max_examples=100)`).
Tag format in comments: `# Feature: projects-registry, Property {N}: {property_text}`

#### Property Test 1 — FormSchema Round-Trip (Property 1)

```python
# Feature: projects-registry, Property 1: FormSchema serialization round-trip
@given(form_schema_strategy())
@settings(max_examples=200)
def test_form_schema_round_trip(schema: FormSchema) -> None:
    serialized = json.dumps(asdict(schema))
    deserialized = deserialize_form_schema(json.loads(serialized))
    assert deserialized == schema
```

The `form_schema_strategy()` generates `FormSchema` objects with:
- 0–20 `CustomField` instances
- Random `FieldType` values
- For poll types: 2–10 options
- Unique field IDs
- `question` strings up to 500 chars

#### Property Test 2 — Subscription Uniqueness Invariant (Property 6)

```python
# Feature: projects-registry, Property 6: Subscription uniqueness invariant
@given(
    person_id=ulid_strategy(),
    project_id=ulid_strategy(),
    n_attempts=st.integers(min_value=2, max_value=5),
)
@settings(max_examples=100)
async def test_subscription_uniqueness(person_id, project_id, n_attempts) -> None:
    # In-memory subscription store
    store = InMemorySubscriptionRepository()
    service = SubscriptionService(store, mock_project_repo(), mock_event_pub())

    # First subscription succeeds
    await service.subscribe(
        CreateSubscriptionCommand(project_id=project_id, person_id=person_id),
        requester_id=person_id, is_super_admin=False,
    )

    # All subsequent attempts must raise ConflictError
    for _ in range(n_attempts - 1):
        with pytest.raises(ConflictError) as exc_info:
            await service.subscribe(
                CreateSubscriptionCommand(project_id=project_id, person_id=person_id),
                requester_id=person_id, is_super_admin=False,
            )
        assert exc_info.value.error_code == "SUBSCRIPTION_ALREADY_EXISTS"

    # Exactly one non-cancelled subscription exists
    subs = await store.list_by_person(person_id)
    active_or_pending = [s for s in subs if s.status != SubscriptionStatus.CANCELLED]
    assert len(active_or_pending) == 1
```

#### Property Test 3 — Participant Count Invariant (Property 5)

```python
# Feature: projects-registry, Property 5: Participant count invariant
@given(
    n_approvals=st.integers(min_value=0, max_value=10),
    n_cancellations=st.integers(min_value=0, max_value=5),
)
@settings(max_examples=100)
async def test_participant_count_invariant(n_approvals, n_cancellations) -> None:
    n_cancellations = min(n_cancellations, n_approvals)
    # ... create project, approve n_approvals subscriptions, cancel n_cancellations
    # Assert project.current_participants == n_approvals - n_cancellations
    # Assert count matches actual active subscriptions in repository
```

#### Property Test 4 — Public Subscribe Always Pending (Property 13)

```python
# Feature: projects-registry, Property 13: Public subscription always pending
@given(person_data=person_strategy(), project_id=ulid_strategy())
@settings(max_examples=100)
async def test_public_subscribe_always_pending(person_data, project_id) -> None:
    # ... call public_service.subscribe with any person data
    # Assert resulting subscription.status == SubscriptionStatus.PENDING
```

#### Property Test 5 — Input Length Validation (Property 16)

```python
# Feature: projects-registry, Property 16: Input length validation
@given(
    name=st.text(min_size=201, max_size=500),
)
@settings(max_examples=100)
async def test_project_name_too_long_rejected(name) -> None:
    with pytest.raises(ValidationError) as exc_info:
        await project_service.create(
            CreateProjectCommand(name=name, description="valid", max_participants=10, ...),
            requester_id="01J...",
        )
    assert exc_info.value.error_code == "VALIDATION_ERROR"
```

### Integration Testing (moto)

```python
@pytest.fixture
def projects_table():
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName="ugsys-projects-test",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "status", "AttributeType": "S"},
                {"AttributeName": "status_created_at", "AttributeType": "S"},
                {"AttributeName": "created_by", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "status-index",
                    "KeySchema": [
                        {"AttributeName": "status", "KeyType": "HASH"},
                        {"AttributeName": "status_created_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "created_by-index",
                    "KeySchema": [{"AttributeName": "created_by", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield client
```

Integration tests must cover:
- `_to_item` / `_from_item` round-trips for all entity fields including optional ones
- Backward compatibility: items missing new optional fields deserialize with safe defaults
- `ClientError` wrapping: verify `RepositoryError` is raised (not raw `ClientError`)
- GSI queries: `list_public` uses status-index, `list_by_project` uses project-index
- Duplicate detection via `person-project-index` GSI



---

## Public Frontend Architecture (React SPA)

### Overview

The public frontend is a React 19 SPA served from `ugsys-projects-registry/web/`. It replaces the existing Astro + React app from `Registry/registry-frontend` — a lift-and-shift of all React components into a pure Vite-powered SPA. Admin flows are excluded (deferred to `ugsys-admin-panel` in Phase 4).

### Architecture Decision

The existing Registry frontend uses Astro with `client:only="react"` on every page, gaining zero SSR benefit. Island architecture fights against SPA behavior (shared auth state, navigation, modals). All components are already React 19 + TypeScript. Dropping Astro and using React Router + Vite aligns with the admin panel stack (React + Vite + FSD), giving the team one frontend paradigm.

### System Architecture Diagram (Frontend)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AWS Cloud                                      │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                     CloudFront Distribution                          │  │
│  │                     https://cbba.cloud.org.bo                        │  │
│  │                                                                      │  │
│  │  ┌──────────────────┐    ┌────────────────────────────────────────┐ │  │
│  │  │  S3 Bucket        │    │  Origin: API Gateway                   │ │  │
│  │  │  ugsys-frontend   │    │  /api/v1/* → projects-registry Lambda │ │  │
│  │  │  /{env}           │    │  /api/v1/auth/* → identity-manager    │ │  │
│  │  │                   │    │                    Lambda              │ │  │
│  │  │  index.html       │    └────────────────────────────────────────┘ │  │
│  │  │  /assets/*        │                                               │  │
│  │  └──────────────────┘                                                │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  Browser (React SPA)                                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  React Router                                                        │  │
│  │  ├── /                    → HomePage (ProjectShowcase)               │  │
│  │  ├── /login               → LoginPage                               │  │
│  │  ├── /register            → RegisterPage                            │  │
│  │  ├── /reset-password/:token → ResetPasswordPage                     │  │
│  │  ├── /subscribe/:projectId → SubscribePage                          │  │
│  │  └── /dashboard           → DashboardPage (protected)               │  │
│  │                                                                      │  │
│  │  Services Layer                                                      │  │
│  │  ├── httpClient.ts        → Bearer token injection, 401 refresh     │  │
│  │  ├── projectApi.ts        → GET /api/v1/projects/public, etc.       │  │
│  │  ├── subscriptionApi.ts   → POST /api/v1/projects/{id}/subscriptions│  │
│  │  ├── authService.ts       → POST /api/v1/auth/login, refresh, etc.  │  │
│  │  └── formApi.ts           → POST /api/v1/form-submissions           │  │
│  │                                                                      │  │
│  │  Auth Store (nanostores)                                             │  │
│  │  ├── $user, $isAuthenticated, $isLoading                            │  │
│  │  ├── login(), logout(), initializeAuth()                            │  │
│  │  └── Token refresh on 401 → force logout on failure                 │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
web/
├── public/                        # Static assets (favicon, robots.txt)
├── src/
│   ├── app/                       # App shell, router config, providers
│   │   ├── App.tsx                # Root component with RouterProvider
│   │   ├── router.tsx             # React Router route definitions
│   │   └── providers.tsx          # Context providers (Toast, Auth)
│   ├── pages/                     # Route-level page components
│   │   ├── HomePage.tsx           # Project showcase (default route)
│   │   ├── LoginPage.tsx          # Login form
│   │   ├── RegisterPage.tsx       # Registration form
│   │   ├── ResetPasswordPage.tsx  # Password reset with token
│   │   ├── DashboardPage.tsx      # User dashboard (protected)
│   │   └── SubscribePage.tsx      # Public + authenticated subscription
│   ├── components/                # Shared UI components
│   │   ├── projects/              # ProjectCard, ProjectGrid, ProjectList, ProjectCompact
│   │   ├── forms/                 # DynamicFormRenderer, SubscriptionForm
│   │   ├── auth/                  # LoginForm, RegisterForm, ForgotPasswordModal
│   │   ├── dashboard/             # SubscriptionList, ProfileSection, PasswordChange
│   │   └── ui/                    # Button, Modal, Toast, Pagination, ViewToggle, LoadingSpinner
│   ├── services/                  # API client modules
│   │   ├── httpClient.ts          # Singleton HTTP client with auth interceptor
│   │   ├── projectApi.ts          # Project CRUD + public listing
│   │   ├── subscriptionApi.ts     # Subscription operations + check
│   │   ├── authService.ts         # Login, register, refresh, forgot/reset password
│   │   └── formApi.ts             # Form submission
│   ├── stores/                    # State management (nanostores)
│   │   ├── authStore.ts           # $user, $isAuthenticated, login(), logout()
│   │   └── toastStore.ts          # Toast notification queue
│   ├── hooks/                     # Custom React hooks
│   │   ├── useAuth.ts             # Auth state hook wrapping authStore
│   │   ├── useProjects.ts         # Project fetching with pagination
│   │   ├── usePagination.ts       # Generic pagination logic
│   │   └── useProtectedRoute.ts   # Redirect to login if unauthenticated
│   ├── types/                     # TypeScript interfaces
│   │   ├── project.ts             # Project, Subscription, ProjectImage
│   │   ├── auth.ts                # User, LoginRequest, RegisterRequest, TokenPair
│   │   ├── form.ts                # FormSchema, CustomField, FormSubmission
│   │   └── api.ts                 # ApiResponse, ApiError, PaginatedResponse
│   └── utils/                     # Utilities
│       ├── dateUtils.ts           # Date formatting helpers
│       ├── errorHandling.ts       # API error → toast mapping
│       ├── sanitize.ts            # HTML/XSS sanitization for user inputs
│       └── logger.ts              # Structured console logger (dev only)
├── index.html                     # SPA entry point
├── vite.config.ts                 # Vite configuration
├── tailwind.config.ts             # Tailwind CSS configuration
├── tsconfig.json                  # TypeScript configuration
├── eslint.config.js               # ESLint flat config
├── package.json                   # Dependencies and scripts
└── .env.example                   # VITE_API_BASE_URL, VITE_AUTH_API_URL
```

### Key Components

#### `httpClient.ts` — Singleton HTTP Client

Wraps `fetch` (or a lightweight library like `ky`) with:
- Automatic `Authorization: Bearer <token>` injection from auth store
- `X-Request-ID` header (UUID v4) on every request for correlation
- 401 interceptor: attempt token refresh → retry original request → force logout on failure
- Response parsing: unwrap `{ data, meta }` envelope on success, extract `{ error, message }` on failure
- Request timeout: 15 seconds
- Base URL from `VITE_API_BASE_URL` environment variable

```typescript
// services/httpClient.ts — simplified interface
interface HttpClient {
  get<T>(path: string, options?: RequestOptions): Promise<T>;
  post<T>(path: string, body: unknown, options?: RequestOptions): Promise<T>;
  put<T>(path: string, body: unknown, options?: RequestOptions): Promise<T>;
  delete<T>(path: string, options?: RequestOptions): Promise<T>;
}
```

#### `authStore.ts` — Auth State (nanostores)

```typescript
// stores/authStore.ts
import { atom, computed } from 'nanostores';

interface AuthUser {
  id: string;
  email: string;
  fullName: string;
  roles: string[];
}

const $user = atom<AuthUser | null>(null);
const $isLoading = atom<boolean>(true);
const $isAuthenticated = computed($user, (user) => user !== null);

function initializeAuth(): void {
  // Read tokens from localStorage, validate expiry, set $user
}

async function login(email: string, password: string): Promise<void> {
  // POST /api/v1/auth/login → store tokens → set $user
}

function logout(): void {
  // Clear localStorage tokens → set $user to null → redirect to /
}
```

#### `DynamicFormRenderer` — Per-Project Custom Fields

Renders `FormSchema` fields as appropriate HTML inputs:

| `FieldType` | Rendered As |
|-------------|-------------|
| `text` | `<input type="text">` |
| `textarea` | `<textarea>` |
| `poll_single` | Radio button group |
| `poll_multiple` | Checkbox group |
| `date` | `<input type="date">` |
| `number` | `<input type="number">` |

Required fields show a visual indicator and are validated client-side before submission. Validation errors from the API (`FORM_SUBMISSION_INVALID_RESPONSE`) are mapped to inline field errors.

#### `ProjectShowcase` — Three View Modes

The project listing supports three view modes persisted in `localStorage`:

| Mode | Layout | Items per page |
|------|--------|----------------|
| Grid | 3-column card grid (responsive) | 12 |
| List | Full-width rows with details | 20 |
| Compact | Dense table-like rows | 20 |

Each project card/row displays: name, description (truncated), category badge, participant count (`current / max`), date range, status badge, and thumbnail image (if available).

### Routing

```typescript
// app/router.tsx
const routes = [
  { path: '/', element: <HomePage /> },
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  { path: '/reset-password/:token', element: <ResetPasswordPage /> },
  { path: '/subscribe/:projectId', element: <SubscribePage /> },
  { path: '/dashboard', element: <ProtectedRoute><DashboardPage /></ProtectedRoute> },
  { path: '*', element: <Navigate to="/" /> },
];
```

`ProtectedRoute` checks `$isAuthenticated` — redirects to `/login` if false, passing the intended destination as a query parameter for post-login redirect.

### Auth Flow

```
Login:
  POST /api/v1/auth/login → { access_token, refresh_token }
  → Store in localStorage → Set $user from token claims → Redirect to /dashboard

Register:
  POST /api/v1/auth/register → 201
  → Redirect to /login with success message

Token Refresh (on 401):
  POST /api/v1/auth/refresh { refresh_token }
  → Update localStorage → Retry original request
  → On failure: logout() → Redirect to /login

Forgot Password:
  POST /api/v1/auth/forgot-password { email }
  → Display "check your email" message

Reset Password:
  POST /api/v1/auth/reset-password { token, new_password }
  → Redirect to /login with success message
```

### Public Subscription Flow

```
User clicks "Subscribe" on project card
  │
  ├─ Authenticated? YES
  │   └─ POST /api/v1/projects/{id}/subscriptions (with JWT)
  │       ├─ 201 → Success toast, update UI
  │       └─ 409 → "Already subscribed" message
  │
  └─ Authenticated? NO
      └─ Navigate to /subscribe/:projectId
          └─ Render SubscriptionForm (email, name, notes + dynamic form)
              └─ On submit:
                  POST /api/v1/public/check-email { email }
                  │
                  ├─ exists: false
                  │   └─ POST /api/v1/public/subscribe { email, projectId, ... }
                  │       └─ 201 → "Account created, subscription pending approval"
                  │
                  └─ exists: true
                      └─ POST /api/v1/subscriptions/check { personId, projectId }
                          ├─ exists: true  → "Already subscribed — login to view status"
                          └─ exists: false → "Please login to subscribe"
```

### API Integration Map

| Frontend Action | API Call | Auth |
|-----------------|----------|------|
| Load project showcase | `GET /api/v1/projects/public` | None |
| View project detail | `GET /api/v1/projects/{id}` | JWT |
| Public subscribe | `POST /api/v1/public/subscribe` | None |
| Check email | `POST /api/v1/public/check-email` | None |
| Check subscription | `POST /api/v1/subscriptions/check` | JWT |
| Authenticated subscribe | `POST /api/v1/projects/{id}/subscriptions` | JWT |
| Submit dynamic form | `POST /api/v1/form-submissions` | JWT |
| Get my subscriptions | `GET /api/v1/subscriptions/person/{id}` | JWT |
| Login | `POST /api/v1/auth/login` | None |
| Register | `POST /api/v1/auth/register` | None |
| Refresh token | `POST /api/v1/auth/refresh` | Refresh token |
| Forgot password | `POST /api/v1/auth/forgot-password` | None |
| Reset password | `POST /api/v1/auth/reset-password` | None |
| Change password | `POST /api/v1/auth/change-password` | JWT |

### Deployment Architecture

| Resource | Configuration |
|----------|---------------|
| S3 bucket | `ugsys-frontend-{env}` — static website hosting disabled (CloudFront origin only) |
| CloudFront | Origin: S3 bucket via OAC; custom error response: 403/404 → `/index.html` (200) |
| Domain | `cbba.cloud.org.bo` — ACM certificate in us-east-1 |
| Cache policy | `/assets/*`: `max-age=31536000, immutable`; `index.html`: `no-cache` |
| CSP header | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' https://cdn.cbba.cloud.org.bo; connect-src 'self' https://api.cbba.cloud.org.bo; frame-ancestors 'none'` |

### Environment Variables

```
VITE_API_BASE_URL=https://api.cbba.cloud.org.bo/projects-registry
VITE_AUTH_API_URL=https://api.cbba.cloud.org.bo/identity
```

These are injected at build time by Vite and baked into the static bundle. No runtime secrets exist in the frontend.

### Frontend CI Pipeline

| Step | Tool | Blocks merge? |
|------|------|---------------|
| Lint | ESLint | Yes |
| Typecheck | `tsc --noEmit` | Yes |
| Build | `vite build` | Yes |
| Lighthouse | Lighthouse CI (perf ≥ 80, a11y ≥ 90) | Advisory |
| Secret scan | Gitleaks | Yes |

### Dependencies (package.json)

```json
{
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^7.0.0",
    "nanostores": "^0.11.0",
    "@nanostores/react": "^0.8.0",
    "tailwindcss": "^4.0.0"
  },
  "devDependencies": {
    "vite": "^6.0.0",
    "typescript": "^5.7.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.0.0",
    "eslint": "^9.0.0",
    "@eslint/js": "^9.0.0",
    "typescript-eslint": "^8.0.0",
    "autoprefixer": "^10.0.0",
    "postcss": "^8.0.0"
  }
}
```

### Correctness Properties (Frontend)

### Property 23: Public subscription always creates pending status

*For any* unauthenticated subscription via `POST /api/v1/public/subscribe`, the frontend must display the subscription as "pending approval" regardless of any response data — the UI must never show a public subscription as "active".

**Validates: Requirements 23.3, 7.7**

### Property 24: Auth token lifecycle

*For any* sequence of API calls, the `httpClient` must never send a request without a valid token on authenticated endpoints, must attempt exactly one refresh on 401, and must force logout if the refresh fails — never entering an infinite refresh loop.

**Validates: Requirements 25.6, 28.3**

### Property 25: Dynamic form field rendering completeness

*For any* valid `FormSchema` with N fields (N ≤ 20), the `DynamicFormRenderer` must render exactly N input elements, each matching the field's `FieldType`, with required indicators on all fields where `required = true`.

**Validates: Requirements 27.1, 27.2**

### Property 26: View mode persistence

*For any* view mode selection (grid, list, compact), refreshing the page must restore the same view mode from `localStorage`.

**Validates: Requirements 22.2**

### Property 27: Error message safety

*For any* API error response, the frontend must display only the `message` field from the error envelope — never raw HTTP status codes, stack traces, internal error codes, or JSON payloads.

**Validates: Requirements 22.6, 23.9, 25.7**


## Backend Deployment

### Container Image Packaging

The service is deployed as a Lambda container image (not a zip package). This is the chosen approach for all `ugsys-*` services.

**Dockerfile** (`Dockerfile.lambda` at repo root):
- Base image: `public.ecr.aws/lambda/python:3.13`
- Installs dependencies via `uv pip install --system`
- Entry point: `handler.handler` (Mangum adapter in `handler.py`)

**Lambda entry point** (`handler.py` at repo root):
```python
from mangum import Mangum
from src.main import app

handler = Mangum(app, lifespan="on")
```

### ECR Repository

| Property | Value |
|----------|-------|
| Registry | `142728997126.dkr.ecr.us-east-1.amazonaws.com` |
| Repository | `ugsys-projects-registry` |
| Image tag pattern | `main-{short-sha}` (also tagged `latest`) |

The ECR repository and Lambda function are provisioned by `ugsys-platform-infrastructure` (`ProjectsRegistryStack`). The service repo has no CDK code — it only builds and pushes images.

### Deploy Workflow (`.github/workflows/deploy.yml`)

Triggered on merge to `main`. Requires `environment: prod` gate approval.

Steps:
1. Configure AWS credentials via OIDC (`AWS_ROLE_ARN` secret, role `ugsys-github-deploy-ugsys-projects-registry`)
2. Login to ECR: `aws ecr get-login-password | docker login`
3. Build image: `docker build -f Dockerfile.lambda -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .`
4. Tag as `latest`: `docker tag ... :latest`
5. Push both tags to ECR
6. Update Lambda: `aws lambda update-function-code --function-name ugsys-projects-registry-prod --image-uri $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG`
7. Notify Slack (`slackapi/slack-github-action@v2.0.0`, channel `C0AE6QV0URH`, username `ugsys CI/CD`)

Environment variables hardcoded in the workflow (not secrets):
- `ECR_REGISTRY: 142728997126.dkr.ecr.us-east-1.amazonaws.com`
- `ECR_REPOSITORY: ugsys-projects-registry`

Only `AWS_ROLE_ARN` and `SLACK_BOT_TOKEN` are GitHub secrets.

### Platform Infrastructure Coupling

The service repo is decoupled from `ugsys-platform-infrastructure`:
- The platform infra CDK stack provisions the ECR repo, Lambda function (`DockerImageFunction`), DynamoDB tables, and S3 images bucket
- The service repo only pushes images and calls `lambda update-function-code --image-uri`
- No CDK code lives in this repo

### DynamoDB Tables (provisioned by platform infra)

| Table | Name pattern |
|-------|-------------|
| Projects | `ugsys-projects-{env}` |
| Subscriptions | `ugsys-subscriptions-{env}` |
| Form Submissions | `ugsys-form-submissions-{env}` |

### S3 Images Bucket (provisioned by platform infra)

| Property | Value |
|----------|-------|
| Bucket name | `ugsys-images-{env}` |
| Access | Lambda IAM role only (no public access) |
| CDN | CloudFront at `cdn.cbba.cloud.org.bo` |