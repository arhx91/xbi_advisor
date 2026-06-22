"""Pydantic schema for BI tool properties — mirrors the structure of the tool YAML files."""

from typing import Any

from pydantic import BaseModel, ConfigDict

# --- Nested Models ---


class AccessControls(BaseModel):
    model_config = ConfigDict(extra="ignore")
    row_level_security: bool | None = None
    field_level_security: bool | None = None
    role_based_permissions: bool | None = None


class Security(BaseModel):
    model_config = ConfigDict(extra="ignore")
    access_controls: AccessControls | None = None
    identity: str | None = None
    encryption: str | None = None
    tool_maturity: str | None = None
    compliance_certifications: list[str] | None = None


class AuditCapabilities(BaseModel):
    model_config = ConfigDict(extra="ignore")
    usage_tracking: bool | None = None
    change_history: bool | None = None
    access_logs: bool | None = None


class DataGovernance(BaseModel):
    model_config = ConfigDict(extra="ignore")
    centralized_semantic_layer: bool | None = None
    data_dictionary: bool | None = None
    metadata_management: bool | None = None
    data_lineage: bool | None = None
    audit_capabilities: AuditCapabilities | None = None
    # Support for quality_monitoring if it appears here in some versions
    quality_monitoring: dict[str, Any] | None = None


class Validation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    rules_required: bool | None = None
    schema_enforcement: bool | None = None


class Monitoring(BaseModel):
    model_config = ConfigDict(extra="ignore")
    dashboards: bool | None = None
    automated_alerts: bool | None = None


class Profiling(BaseModel):
    model_config = ConfigDict(extra="ignore")
    data_statistics: bool | None = None
    anomaly_detection: bool | None = None


class DataQuality(BaseModel):
    model_config = ConfigDict(extra="ignore")
    validation: Validation | None = None
    monitoring: Monitoring | None = None
    profiling: Profiling | None = None
    freshness_monitoring: bool | None = None


class DeploymentPipelines(BaseModel):
    model_config = ConfigDict(extra="ignore")
    supported: bool | str | None = None


class CICD(BaseModel):
    model_config = ConfigDict(extra="ignore")
    APIs: bool | None = None


class Implementation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    embedded_analytics: bool | None = None
    on_prem_or_not: list[str] | None = None
    deployment_pipelines: DeploymentPipelines | None = None
    CI_CD: CICD | None = None


class ExternalSharing(BaseModel):
    model_config = ConfigDict(extra="ignore")
    supported: bool | None = None


class Serving(BaseModel):
    model_config = ConfigDict(extra="ignore")
    internal_sharing: bool | None = None
    # Support both boolean (legacy) and dict (Power BI)
    external_sharing: bool | ExternalSharing | None = None
    automated_reports: bool | None = None
    export_formats: list[str] | None = None


class Visualization(BaseModel):
    model_config = ConfigDict(extra="ignore")
    out_of_the_box_features: list[str] | None = None
    custom_visuals: str | None = None


class Workflow(BaseModel):
    model_config = ConfigDict(extra="ignore")
    approvals: bool | None = None
    versioning: str | None = None
    environments: str | None = None


# --- Main Model ---


class BiProperties(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str

    # Target: Dict. Union used to allow legacy Lists without crashing.
    pros: list[str] | dict[str, Any] | None = None
    cons: list[str] | dict[str, Any] | None = None

    # Target: Pricing Block (Dict)
    pricing: dict[str, Any] | None = None

    # Target: Tech Stack
    tech_stack: list[str] | None = None

    security: Security | None = None
    tool_maturity: str | None = None
    data_governance: DataGovernance | None = None
    data_quality_monitoring_alerting: DataQuality | None = None
    implementation_deployment: Implementation | None = None
    serving_consumption: Serving | None = None
    visualization: Visualization | None = None
    workflow_management: Workflow | None = None
