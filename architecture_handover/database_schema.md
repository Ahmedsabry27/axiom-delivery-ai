# Database Schema

Generated from current SQLAlchemy mapped models. Types reflect Python annotations; declared relationships are identified from `ForeignKey`.

## `actions` — `Action`

Source: `backend/app/database/models/action.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `int` | PK |
| `permissions` | `dict` | — |
| `status` | `str` | — |
| `usage` | `int` | — |
| `created_at` | `datetime` | — |

## `agent_access_assignments` — `AgentAccessAssignment`

Source: `backend/app/database/models/agent_assignment.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `agent_id` | `int` | FK→agents.id |
| `tenant_id` | `str` | — |
| `subject_type` | `str` | — |
| `subject_id` | `str` | — |
| `action` | `str` | — |
| `enabled` | `bool` | — |
| `added_by` | `str` | — |
| `created_at` | `datetime` | — |

## `agent_activity_events` — `AgentActivityEvent`

Source: `backend/app/database/models/agent.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `agent_id` | `int` | FK→agents.id |
| `tenant_id` | `str` | — |
| `event_type` | `str` | — |
| `actor_id` | `str` | — |
| `agent_version` | `int | None` | — |
| `summary` | `dict` | — |
| `created_at` | `datetime` | — |

## `agent_continuations` — `AgentContinuation`

Source: `backend/app/database/models/agent_execution.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `tenant_id` | `str` | — |
| `execution_id` | `str` | FK→agent_executions.id |
| `conversation_id` | `str | None` | — |
| `workflow_id` | `str | None` | — |
| `agent_id` | `int` | FK→agents.id |
| `agent_version` | `int` | — |
| `kind` | `str` | — |
| `tool_name` | `str | None` | — |
| `tool_version` | `str | None` | — |
| `schema` | `dict` | — |
| `known_values` | `dict` | — |
| `missing_fields` | `list` | — |
| `safe_question` | `str | None` | — |
| `alternatives` | `list` | — |
| `required_approver` | `str | None` | — |
| `input_fingerprint` | `str | None` | — |
| `status` | `str` | — |
| `resume_token_hash` | `str` | UNIQUE |
| `response` | `dict` | — |
| `created_at` | `datetime` | — |
| `expires_at` | `datetime` | — |
| `consumed_at` | `datetime | None` | — |
| `cancelled_at` | `datetime | None` | — |

## `agent_execution_settings` — `AgentExecutionSetting`

Source: `backend/app/database/models/agent_assignment.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `agent_id` | `int` | FK→agents.id |
| `tenant_id` | `str` | — |
| `max_steps` | `int` | — |
| `timeout_seconds` | `int` | — |
| `cost_limit` | `float | None` | — |
| `risk_limit` | `str` | — |
| `updated_by` | `str` | — |
| `updated_at` | `datetime` | — |

## `agent_executions` — `AgentExecution`

Source: `backend/app/database/models/agent_execution.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `runtime_execution_id` | `str | None` | — |
| `tenant_id` | `str` | — |
| `agent_id` | `int` | FK→agents.id |
| `agent_uuid` | `str` | — |
| `agent_version` | `int` | — |
| `actor_id` | `str` | — |
| `service_identity` | `str | None` | — |
| `conversation_id` | `str | None` | — |
| `workflow_id` | `str | None` | — |
| `discovery_id` | `str | None` | — |
| `parent_execution_id` | `str | None` | FK→agent_executions.id |
| `status` | `str` | — |
| `current_phase` | `str` | — |
| `request_summary` | `str` | — |
| `input_summary` | `dict` | — |
| `output_summary` | `dict` | — |
| `model_provider` | `str` | — |
| `model_name` | `str` | — |
| `planner` | `str` | — |
| `selected_tools` | `list` | — |
| `tool_execution_ids` | `list` | — |
| `knowledge_source_ids` | `list` | — |
| `runtime_metadata` | `dict` | — |
| `token_usage` | `dict` | — |
| `estimated_cost` | `float | None` | — |
| `actual_cost` | `float | None` | — |
| `currency` | `str` | — |
| `error_code` | `str | None` | — |
| `safe_error_message` | `str | None` | — |
| `correlation_id` | `str` | UNIQUE |
| `trace_id` | `str` | — |
| `test_mode` | `bool` | — |
| `started_at` | `datetime` | — |
| `completed_at` | `datetime | None` | — |
| `cancelled_at` | `datetime | None` | — |
| `duration_ms` | `float | None` | — |
| `created_at` | `datetime` | — |
| `updated_at` | `datetime` | — |

## `agent_knowledge_assignments` — `AgentKnowledgeAssignment`

Source: `backend/app/database/models/agent_assignment.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `agent_id` | `int` | FK→agents.id |
| `tenant_id` | `str` | — |
| `knowledge_source_id` | `int` | FK→knowledge_sources.id |
| `source_type` | `str` | — |
| `access_mode` | `str` | — |
| `readiness_required` | `bool` | — |
| `enabled` | `bool` | — |
| `added_by` | `str` | — |
| `created_at` | `datetime` | — |

## `agent_tool_assignments` — `AgentToolAssignment`

Source: `backend/app/database/models/agent_assignment.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `agent_id` | `int` | FK→agents.id |
| `agent_version` | `int | None` | — |
| `tenant_id` | `str` | — |
| `tool_name` | `str` | — |
| `version_restriction` | `str | None` | — |
| `assignment_action` | `str` | — |
| `enabled` | `bool` | — |
| `risk_mode` | `str` | — |
| `approval_required` | `bool` | — |
| `added_by` | `str` | — |
| `created_at` | `datetime` | — |

## `agent_versions` — `AgentVersion`

Source: `backend/app/database/models/agent.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `agent_id` | `int` | FK→agents.id |
| `tenant_id` | `str` | — |
| `version` | `int` | — |
| `instructions` | `str` | — |
| `model_configuration` | `dict` | — |
| `planner_configuration` | `dict` | — |
| `memory_configuration` | `dict` | — |
| `execution_limits` | `dict` | — |
| `tool_discovery_configuration` | `dict` | — |
| `configuration_snapshot` | `dict` | — |
| `change_note` | `str` | — |
| `created_by` | `str` | — |
| `created_at` | `datetime` | — |
| `published` | `bool` | — |

## `agents` — `Agent`

Source: `backend/app/database/models/agent.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `int` | PK |
| `uuid` | `str` | UNIQUE |
| `tenant_id` | `str` | — |
| `slug` | `str` | — |
| `name` | `str` | — |
| `description` | `str` | — |
| `owner_id` | `str` | — |
| `lifecycle_status` | `str` | — |
| `operational_health` | `str` | — |
| `current_version` | `int` | — |
| `published_version` | `int | None` | — |
| `model_configuration_ref` | `str | None` | — |
| `planner_configuration` | `dict` | — |
| `instruction_version` | `int` | — |
| `tool_discovery_mode` | `str` | — |
| `memory_configuration` | `dict` | — |
| `max_execution_steps` | `int` | — |
| `execution_timeout_seconds` | `int` | — |
| `cost_limit` | `float | None` | — |
| `risk_limit` | `str` | — |
| `environment_restrictions` | `list` | — |
| `configuration` | `str` | — |
| `created_at` | `datetime` | — |
| `updated_at` | `datetime` | — |
| `created_by` | `str` | — |
| `updated_by` | `str` | — |
| `published_at` | `datetime | None` | — |
| `archived_at` | `datetime | None` | — |
| `lock_version` | `int` | — |
| `deleted_at` | `datetime | None` | — |
| `deleted_by` | `str | None` | — |
| `status` | `str` | — |
| `health` | `str` | — |

## `approval_requests` — `ApprovalRequest`

Source: `backend/app/database/models/governance_workflow.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `tenant_id` | `str` | — |
| `tool_name` | `str` | — |
| `tool_version` | `str` | — |
| `discovery_id` | `str | None` | — |
| `execution_id` | `str | None` | — |
| `conversation_id` | `str | None` | — |
| `requester_id` | `str` | — |
| `requester_agent_id` | `str | None` | — |
| `policy_id` | `str | None` | — |
| `policy_version` | `int | None` | — |
| `required_approver_role` | `str | None` | — |
| `required_approver_group` | `str | None` | — |
| `separation_of_duties` | `bool` | — |
| `risk_level` | `str` | — |
| `environment` | `str` | — |
| `safe_action_summary` | `dict` | — |
| `input_fingerprint` | `str` | — |
| `status` | `str` | — |
| `created_at` | `datetime` | — |
| `expires_at` | `datetime` | — |
| `approver_id` | `str | None` | — |
| `decision` | `str | None` | — |
| `decision_reason` | `str | None` | — |
| `decided_at` | `datetime | None` | — |
| `resume_token_hash` | `str` | — |
| `consumed_at` | `datetime | None` | — |
| `revoked_at` | `datetime | None` | — |
| `audit_metadata` | `dict` | — |
| `state_version` | `int` | — |

## `audit_logs` — `AuditLog`

Source: `backend/app/database/models/audit.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `int` | PK |
| `before_summary` | `dict | None` | — |
| `after_summary` | `dict | None` | — |
| `metadata_json` | `dict | None` | — |
| `created_at` | `datetime | None` | — |

## `clarification_requests` — `ClarificationRequest`

Source: `backend/app/database/models/governance_workflow.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `tenant_id` | `str` | — |
| `conversation_id` | `str | None` | — |
| `discovery_id` | `str | None` | — |
| `tool_name` | `str` | — |
| `tool_version` | `str` | — |
| `candidate_alternatives` | `list` | — |
| `question` | `str` | — |
| `input_schema` | `dict` | — |
| `known_values` | `dict` | — |
| `missing_fields` | `list` | — |
| `status` | `str` | — |
| `created_at` | `datetime` | — |
| `expires_at` | `datetime` | — |
| `user_response` | `dict | None` | — |
| `resume_token_hash` | `str` | — |
| `consumed_at` | `datetime | None` | — |
| `requester_id` | `str` | — |
| `audit_metadata` | `dict` | — |
| `state_version` | `int` | — |

## `conversations` — `Conversation`

Source: `backend/app/models/conversation.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `uuid.UUID` | PK |
| `title` | `str` | — |
| `user_id` | `str` | — |
| `tenant_id` | `str` | — |
| `agent_uuid` | `str | None` | — |
| `agent_version` | `int | None` | — |
| `is_pinned` | `bool` | — |
| `created_at` | `datetime` | — |
| `updated_at` | `datetime` | — |

## `integration_configurations` — `IntegrationConfiguration`

Source: `backend/app/database/models/tool.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `tenant_id` | `str` | — |
| `provider` | `str` | — |
| `display_name` | `str` | — |
| `base_url` | `str | None` | — |
| `account_identifier` | `str | None` | — |
| `auth_method` | `str | None` | — |
| `secret_reference` | `str | None` | — |
| `safe_metadata` | `dict` | — |
| `enabled` | `bool` | — |
| `health_status` | `str` | — |
| `health_message` | `str | None` | — |
| `last_verified_at` | `datetime | None` | — |
| `created_at` | `datetime` | — |
| `updated_at` | `datetime` | — |

## `knowledge_sources` — `KnowledgeSource`

Source: `backend/app/database/models/knowledge_source.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `int` | PK |
| `tenant_id` | `str` | — |
| `owner_id` | `str` | — |
| `name` | `str` | — |
| `source_type` | `str` | — |
| `location` | `str | None` | — |
| `readiness_status` | `str` | — |
| `health_status` | `str` | — |
| `last_synchronized_at` | `datetime | None` | — |
| `created_at` | `datetime` | — |

## `mcp_capabilities` — `MCPCapability`

Source: `backend/app/database/models/mcp.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `server_id` | `str` | FK→mcp_servers.id |
| `tenant_id` | `str` | — |
| `capability_type` | `str` | — |
| `remote_name` | `str` | — |
| `internal_name` | `str` | — |
| `display_name` | `str` | — |
| `description` | `str` | — |
| `uri` | `str | None` | — |
| `mime_type` | `str | None` | — |
| `schema_json` | `dict` | — |
| `safe_metadata` | `dict` | — |
| `fingerprint` | `str` | — |
| `previous_fingerprint` | `str | None` | — |
| `change_status` | `str` | — |
| `risk_level` | `str` | — |
| `permission` | `str` | — |
| `approval_policy` | `str` | — |
| `enabled` | `bool` | — |
| `approved` | `bool` | — |
| `missing` | `bool` | — |
| `first_discovered_at` | `datetime` | — |
| `last_discovered_at` | `datetime` | — |
| `last_synced_at` | `datetime` | — |

## `mcp_servers` — `MCPServer`

Source: `backend/app/database/models/mcp.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `tenant_id` | `str` | — |
| `display_name` | `str` | — |
| `slug` | `str` | — |
| `description` | `str` | — |
| `environment` | `str` | — |
| `server_url` | `str` | — |
| `transport` | `str` | — |
| `auth_type` | `str` | — |
| `secret_reference` | `str | None` | — |
| `auth_config` | `dict` | — |
| `requested_scopes` | `list` | — |
| `granted_scopes` | `list` | — |
| `policy` | `dict` | — |
| `requested_protocol_version` | `str | None` | — |
| `negotiated_protocol_version` | `str | None` | — |
| `sdk_version` | `str` | — |
| `server_name` | `str | None` | — |
| `server_version` | `str | None` | — |
| `capabilities` | `dict` | — |
| `enabled` | `bool` | — |
| `health_status` | `str` | — |
| `sync_status` | `str` | — |
| `last_health_check` | `datetime | None` | — |
| `last_connected_at` | `datetime | None` | — |
| `last_synced_at` | `datetime | None` | — |
| `configuration_version` | `int` | — |
| `created_by` | `str` | — |
| `updated_by` | `str` | — |
| `created_at` | `datetime` | — |
| `updated_at` | `datetime` | — |
| `deleted_at` | `datetime | None` | — |

## `mcp_sync_runs` — `MCPSyncRun`

Source: `backend/app/database/models/mcp.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `server_id` | `str` | FK→mcp_servers.id |
| `tenant_id` | `str` | — |
| `status` | `str` | — |
| `started_at` | `datetime` | — |
| `finished_at` | `datetime | None` | — |
| `added_count` | `int` | — |
| `changed_count` | `int` | — |
| `removed_count` | `int` | — |
| `warning_count` | `int` | — |
| `error_code` | `str | None` | — |
| `safe_error` | `str | None` | — |
| `correlation_id` | `str` | — |

## `messages` — `Message`

Source: `backend/app/models/message.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `uuid.UUID` | PK |
| `conversation_id` | `uuid.UUID` | FK→conversations.id |
| `role` | `str` | — |
| `content` | `str` | — |
| `response_id` | `str | None` | — |
| `created_at` | `datetime` | — |

## `native_connections` — `NativeConnection`

Source: `backend/app/database/models/native_tool.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `tenant_id` | `str` | — |
| `kind` | `str` | — |
| `display_name` | `str` | — |
| `engine` | `str | None` | — |
| `base_url` | `str | None` | — |
| `secret_reference` | `str | None` | — |
| `safe_config` | `dict` | — |
| `enabled` | `bool` | — |
| `health_status` | `str` | — |
| `last_verified_at` | `datetime | None` | — |
| `created_by` | `str` | — |
| `updated_by` | `str` | — |
| `created_at` | `datetime` | — |
| `updated_at` | `datetime` | — |

## `native_file_contents` — `NativeFileContent`

Source: `backend/app/database/models/native_tool.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `int` | PK |
| `file_id` | `str` | FK→native_files.id |
| `tenant_id` | `str` | — |
| `sequence` | `int` | — |
| `section` | `str | None` | — |
| `text` | `str` | — |
| `character_count` | `int` | — |
| `metadata_json` | `dict` | — |

## `native_files` — `NativeFile`

Source: `backend/app/database/models/native_tool.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `tenant_id` | `str` | — |
| `original_filename` | `str` | — |
| `normalized_filename` | `str` | — |
| `object_key` | `str` | — |
| `mime_type` | `str` | — |
| `extension` | `str` | — |
| `byte_size` | `int` | — |
| `checksum` | `str` | — |
| `owner_id` | `str` | — |
| `scan_status` | `str` | — |
| `processing_status` | `str` | — |
| `page_count` | `int | None` | — |
| `extractor_version` | `str | None` | — |
| `error_code` | `str | None` | — |
| `created_at` | `datetime` | — |
| `updated_at` | `datetime` | — |

## `native_notifications` — `NativeNotification`

Source: `backend/app/database/models/native_tool.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `tenant_id` | `str` | — |
| `channel` | `str` | — |
| `actor_id` | `str` | — |
| `recipient_summary` | `dict` | — |
| `subject` | `str | None` | — |
| `safe_message` | `str` | — |
| `status` | `str` | — |
| `approval_state` | `str` | — |
| `provider_message_id` | `str | None` | — |
| `idempotency_key` | `str` | — |
| `failure_code` | `str | None` | — |
| `created_at` | `datetime` | — |
| `sent_at` | `datetime | None` | — |

## `runtime_continuations` — `RuntimeContinuation`

Source: `backend/app/models/runtime_execution.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `uuid.UUID` | PK |
| `execution_id` | `uuid.UUID` | FK→runtime_executions.id |
| `tenant_id` | `str` | — |
| `kind` | `str` | — |
| `status` | `str` | — |
| `schema` | `dict` | — |
| `known_values` | `dict` | — |
| `response` | `dict` | — |
| `required_role` | `str | None` | — |
| `expires_at` | `datetime` | — |
| `created_at` | `datetime` | — |
| `consumed_at` | `datetime | None` | — |

## `runtime_execution_events` — `RuntimeExecutionEvent`

Source: `backend/app/models/runtime_execution.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `uuid.UUID` | PK |
| `execution_id` | `uuid.UUID` | FK→runtime_executions.id |
| `sequence` | `int` | — |
| `event_type` | `str` | — |
| `name` | `str | None` | — |
| `status` | `str | None` | — |
| `description` | `str | None` | — |
| `payload` | `dict` | — |
| `created_at` | `datetime` | — |

## `runtime_executions` — `RuntimeExecution`

Source: `backend/app/models/runtime_execution.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `uuid.UUID` | PK |
| `conversation_id` | `uuid.UUID` | — |
| `workflow_id` | `uuid.UUID` | UNIQUE |
| `user_id` | `str` | — |
| `goal` | `str | None` | — |
| `agent` | `str | None` | — |
| `selected_agent_id` | `str | None` | — |
| `tenant_id` | `str` | — |
| `provider_name` | `str | None` | — |
| `model_name` | `str | None` | — |
| `workspace_id` | `str | None` | — |
| `current_step` | `str | None` | — |
| `runtime_metadata` | `dict` | — |
| `token_usage` | `dict` | — |
| `estimated_cost` | `float | None` | — |
| `actual_cost` | `float | None` | — |
| `waiting_reason` | `str | None` | — |
| `status` | `str` | — |
| `started_at` | `datetime` | — |
| `completed_at` | `datetime | None` | — |
| `duration_ms` | `float | None` | — |
| `steps` | `list` | — |
| `result_message` | `str | None` | — |
| `error` | `str | None` | — |

## `tasks` — `Task`

Source: `backend/app/database/models/task.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `int` | PK |
| `status` | `str` | — |
| `agent` | `str | None` | — |
| `started_at` | `datetime | None` | — |
| `completed_at` | `datetime | None` | — |

## `tool_assignments` — `ToolAssignment`

Source: `backend/app/database/models/tool_discovery.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `tenant_id` | `str` | — |
| `tool_name` | `str` | — |
| `tool_version` | `str | None` | — |
| `subject_type` | `str` | — |
| `subject_id` | `str` | — |
| `action` | `str` | — |
| `decision` | `str` | — |
| `status` | `str` | — |
| `created_by` | `str` | — |
| `created_at` | `datetime` | — |

## `tool_candidate_decisions` — `ToolCandidateDecision`

Source: `backend/app/database/models/tool_discovery.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `discovery_id` | `str` | FK→tool_discovery_events.id |
| `tenant_id` | `str` | — |
| `tool_name` | `str | None` | — |
| `tool_version` | `str | None` | — |
| `eligible` | `bool` | — |
| `exclusion_code` | `str | None` | — |
| `component_scores` | `dict` | — |
| `final_score` | `float` | — |
| `rank` | `int | None` | — |
| `selected` | `bool` | — |

## `tool_definitions` — `ToolDefinition`

Source: `backend/app/database/models/tool.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `tenant_id` | `str` | — |
| `name` | `str` | — |
| `display_name` | `str` | — |
| `description` | `str` | — |
| `category` | `str` | — |
| `provider` | `str` | — |
| `version` | `str` | — |
| `input_schema` | `dict` | — |
| `output_schema` | `dict | None` | — |
| `permissions` | `list` | — |
| `tags` | `list` | — |
| `risk_level` | `str` | — |
| `enabled` | `bool` | — |
| `active` | `bool` | — |
| `deprecated` | `bool` | — |
| `registration_source` | `str` | — |
| `configuration_state` | `str` | — |
| `created_by` | `str` | — |
| `updated_by` | `str` | — |
| `created_at` | `datetime` | — |
| `updated_at` | `datetime` | — |

## `tool_discovery_events` — `ToolDiscoveryEvent`

Source: `backend/app/database/models/tool_discovery.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `tenant_id` | `str` | — |
| `actor_id` | `str` | — |
| `agent_id` | `str | None` | — |
| `conversation_id` | `str | None` | — |
| `safe_intent` | `dict` | — |
| `candidate_count` | `int` | — |
| `eligible_count` | `int` | — |
| `selected_tool` | `str | None` | — |
| `selected_version` | `str | None` | — |
| `confidence` | `str` | — |
| `outcome` | `str` | — |
| `strategy_version` | `str` | — |
| `embedding_model` | `str | None` | — |
| `duration_ms` | `float` | — |
| `correlation_id` | `str` | — |
| `execution_id` | `str | None` | — |
| `created_at` | `datetime` | — |

## `tool_discovery_feedback` — `ToolDiscoveryFeedback`

Source: `backend/app/database/models/tool_discovery.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `discovery_id` | `str` | FK→tool_discovery_events.id |
| `tenant_id` | `str` | — |
| `actor_id` | `str` | — |
| `feedback_type` | `str` | — |
| `selected_tool` | `str | None` | — |
| `alternative_tool` | `str | None` | — |
| `safe_reason` | `str` | — |
| `created_at` | `datetime` | — |

## `tool_executions` — `ToolExecution`

Source: `backend/app/database/models/tool.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `tenant_id` | `str` | — |
| `tool_name` | `str` | — |
| `tool_version` | `str` | — |
| `actor_id` | `str` | — |
| `agent_id` | `str | None` | — |
| `status` | `str` | — |
| `correlation_id` | `str` | — |
| `trace_id` | `str | None` | — |
| `started_at` | `datetime` | — |
| `finished_at` | `datetime | None` | — |
| `duration_ms` | `float | None` | — |
| `input_summary` | `dict` | — |
| `output_summary` | `dict | list | str | None` | — |
| `error_code` | `str | None` | — |
| `error_message` | `str | None` | — |
| `retry_count` | `int` | — |
| `idempotency_key` | `str | None` | — |
| `provider_request_id` | `str | None` | — |

## `tool_governance_policies` — `ToolGovernancePolicy`

Source: `backend/app/database/models/tool_discovery.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `tenant_id` | `str` | — |
| `name` | `str` | — |
| `description` | `str` | — |
| `version` | `int` | — |
| `lifecycle` | `str` | — |
| `conditions` | `list` | — |
| `actions` | `dict` | — |
| `decision` | `str` | — |
| `priority` | `int` | — |
| `change_note` | `str` | — |
| `created_by` | `str` | — |
| `updated_by` | `str` | — |
| `created_at` | `datetime` | — |
| `updated_at` | `datetime` | — |
| `published_at` | `datetime | None` | — |

## `tool_marketplace_profiles` — `ToolMarketplaceProfile`

Source: `backend/app/database/models/tool_discovery.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `tenant_id` | `str` | — |
| `tool_name` | `str` | — |
| `tool_version` | `str` | — |
| `source` | `str` | — |
| `status` | `str` | — |
| `health_status` | `str` | — |
| `environment` | `str` | — |
| `data_classifications` | `list` | — |
| `approval_policy` | `str` | — |
| `estimated_cost` | `float | None` | — |
| `currency` | `str` | — |
| `agent_allowlist` | `list` | — |
| `safe_metadata` | `dict` | — |
| `updated_by` | `str` | — |
| `updated_at` | `datetime` | — |

## `tool_search_index` — `ToolSearchIndex`

Source: `backend/app/database/models/tool_discovery.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `str` | PK |
| `tenant_id` | `str` | — |
| `tool_name` | `str` | — |
| `tool_version` | `str` | — |
| `search_document` | `str` | — |
| `content_fingerprint` | `str` | — |
| `embedding` | `list` | — |
| `embedding_model` | `str` | — |
| `embedding_dimensions` | `int` | — |
| `index_version` | `str` | — |
| `index_status` | `str` | — |
| `safe_error_code` | `str | None` | — |
| `indexed_at` | `datetime` | — |

## `users` — `User`

Source: `backend/app/database/models/user.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `int` | PK |
| `email` | `str` | UNIQUE |
| `name` | `str` | — |
| `role` | `str` | — |
| `tenant_id` | `str` | — |
| `created_at` | `datetime` | — |

## `workflows` — `Workflow`

Source: `backend/app/database/models/workflow.py`

| Column | Type | Constraints/reference |
|---|---|---|
| `id` | `int` | PK |
| `description` | `str | None` | — |
| `assigned_agent` | `str | None` | — |
| `trigger_type` | `str` | — |
| `definition` | `dict` | — |
| `status` | `str` | — |
| `created_at` | `datetime` | — |
| `completed_at` | `datetime | None` | — |
