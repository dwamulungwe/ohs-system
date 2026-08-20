import {
  Activity,
  CheckSquare,
  Bell,
  Building2,
  ClipboardCheck,
  Eye,
  FileCheck2,
  Flame,
  GraduationCap,
  History,
  MapPinned,
  Megaphone,
  Shield,
  ShieldAlert,
  Siren,
  Users,
  Wrench,
  HardHat,
} from 'lucide-react'
import { formatDate, formatDateTime, summarizeList } from '../lib/formatters.js'
import { Badge } from '../components/Badge.jsx'

function renderDateTime(item, key) {
  return formatDateTime(item[key])
}

function renderDate(item, key) {
  return formatDate(item[key])
}

function renderBadge(item, key) {
  return <Badge value={item[key]} />
}

export const resources = [
  {
    key: 'ppe',
    label: 'PPE Management',
    singular: 'PPE Record',
    route: '/ppe',
    icon: HardHat,
    customPage: true,
    description: 'Catalogue, stock, issues, inspections, requests and employee PPE compliance.',
  },
  {
    key: 'sites',
    label: 'Sites',
    singular: 'Site',
    route: '/sites',
    workflowForm: true,
    icon: MapPinned,
    listEndpoint: '/sites',
    detailEndpoint: (id) => `/sites/${id}`,
    description: 'Operational locations connected to the OHS program.',
    columns: [
      { key: 'name', label: 'Name' },
      { key: 'code', label: 'Code' },
      { key: 'address', label: 'Address' },
      { key: 'created_at', label: 'Created', render: (item) => renderDateTime(item, 'created_at') },
    ],
    detailSections: [
      {
        title: 'Site Profile',
        fields: [
          { key: 'name', label: 'Name' },
          { key: 'code', label: 'Code' },
          { key: 'address', label: 'Address' },
          { key: 'created_by_id', label: 'Created By User', type: 'number' },
          { key: 'created_at', label: 'Created At', type: 'datetime' },
          { key: 'updated_at', label: 'Updated At', type: 'datetime' },
        ],
      },
    ],
  },
  {
    key: 'departments',
    label: 'Departments',
    singular: 'Department',
    route: '/departments',
    workflowForm: true,
    icon: Building2,
    listEndpoint: '/departments',
    detailEndpoint: (id) => `/departments/${id}`,
    description: 'Organisation business units and reporting hierarchy.',
    columns: [
      { key: 'name', label: 'Name' },
      { key: 'code', label: 'Code' },
      { key: 'parent_department_id', label: 'Parent', type: 'number' },
      { key: 'manager_user_id', label: 'Manager', type: 'number' },
      { key: 'is_active', label: 'Status', render: (item) => <Badge value={item.is_active ? 'active' : 'inactive'} /> },
    ],
    detailSections: [
      {
        title: 'Department Profile',
        fields: [
          { key: 'name', label: 'Name' },
          { key: 'code', label: 'Code' },
          { key: 'description', label: 'Description', type: 'longtext', fullWidth: true },
          { key: 'parent_department_id', label: 'Parent Department', type: 'number' },
          { key: 'manager_user_id', label: 'Manager', type: 'number' },
          { key: 'is_active', label: 'Active', type: 'boolean' },
          { key: 'created_at', label: 'Created At', type: 'datetime' },
          { key: 'updated_at', label: 'Updated At', type: 'datetime' },
        ],
      },
    ],
  },
  {
    key: 'users',
    label: 'Users',
    singular: 'User',
    route: '/users',
    icon: Users,
    listEndpoint: '/users',
    detailEndpoint: (id) => `/users/${id}`,
    description: 'System users and their assigned enterprise roles.',
    columns: [
      { key: 'full_name', label: 'Name' },
      { key: 'email', label: 'Email' },
      { key: 'phone_number', label: 'Phone' },
      { key: 'primary_role', label: 'Primary Role' },
      { key: 'is_active', label: 'Status', render: (item) => <Badge value={item.is_active ? 'active' : 'inactive'} /> },
      { key: 'assigned_site_id', label: 'Assigned Site', type: 'number' },
    ],
    detailSections: [
      {
        title: 'User Profile',
        fields: [
          { key: 'full_name', label: 'Full Name' },
          { key: 'email', label: 'Email' },
          { key: 'phone_number', label: 'Phone Number' },
          { key: 'primary_role', label: 'Primary Role' },
          { key: 'role_names', label: 'Assigned Roles', type: 'list', fullWidth: true },
          { key: 'assigned_site_id', label: 'Assigned Site', type: 'number' },
          { key: 'is_active', label: 'Active', type: 'boolean' },
          { key: 'created_at', label: 'Created At', type: 'datetime' },
          { key: 'updated_at', label: 'Updated At', type: 'datetime' },
        ],
      },
    ],
  },
  {
    key: 'roles',
    label: 'Roles',
    singular: 'Role',
    route: '/roles',
    icon: Shield,
    listEndpoint: '/roles',
    detailEndpoint: (id) => `/roles/${id}`,
    description: 'Standardized enterprise access roles.',
    columns: [
      { key: 'name', label: 'Name' },
      { key: 'description', label: 'Description' },
      { key: 'created_at', label: 'Created', render: (item) => renderDateTime(item, 'created_at') },
    ],
    detailSections: [
      {
        title: 'Role Definition',
        fields: [
          { key: 'name', label: 'Name' },
          { key: 'description', label: 'Description', type: 'longtext', fullWidth: true },
          { key: 'created_at', label: 'Created At', type: 'datetime' },
          { key: 'updated_at', label: 'Updated At', type: 'datetime' },
        ],
      },
    ],
  },
  {
    key: 'audit-logs',
    label: 'Audit Logs',
    singular: 'Audit Log',
    route: '/audit-logs',
    icon: History,
    listEndpoint: '/audit-logs',
    description: 'Administrative activity trail for sensitive system and workflow events.',
    columns: [
      { key: 'action', label: 'Action' },
      { key: 'resource_type', label: 'Resource Type' },
      { key: 'resource_id', label: 'Resource Id', type: 'number' },
      { key: 'actor_id', label: 'Actor Id', type: 'number' },
      { key: 'created_at', label: 'Created', render: (item) => renderDateTime(item, 'created_at') },
    ],
  },
  {
    key: 'data-imports',
    label: 'Data Imports',
    singular: 'Data Import',
    route: '/data-imports',
    customPage: true,
    icon: History,
    description: 'Preview, validate, and explicitly confirm controlled historical data imports.',
    columns: [],
    detailSections: [],
  },
  {
    key: 'incidents',
    label: 'Incidents',
    singular: 'Incident',
    route: '/incidents',
    customPage: true,
    workflowForm: true,
    icon: Siren,
    attachmentEntityType: 'incident',
    approvalConfig: {
      entityType: 'incident',
      actionType: 'incident_closure',
      requestLabel: 'Request closure approval',
      requestTitle: 'Request Incident Closure Approval',
    },
    listEndpoint: '/incidents',
    detailEndpoint: (id) => `/incidents/${id}`,
    description: 'Reported incidents with severity, status, and evidence metadata.',
    csvExportEndpoint: '/exports/incidents.csv',
    columns: [
      { key: 'incident_reference', label: 'Reference' },
      { key: 'title', label: 'Title' },
      { key: 'incident_type', label: 'Classification', render: (item) => renderBadge(item, 'incident_type') },
      { key: 'status', label: 'Status', render: (item) => renderBadge(item, 'status') },
      { key: 'severity', label: 'Severity', render: (item) => renderBadge(item, 'severity') },
      { key: 'site_id', label: 'Site', type: 'number' },
      { key: 'is_recordable', label: 'Recordable', render: (item) => <Badge value={item.is_recordable ? 'yes' : 'no'} /> },
      { key: 'occurred_at', label: 'Occurred', render: (item) => renderDateTime(item, 'occurred_at') },
    ],
    detailSections: [
      {
        title: 'Incident Snapshot',
        fields: [
          { key: 'title', label: 'Title' },
          { key: 'status', label: 'Status', badge: true },
          { key: 'severity', label: 'Severity', badge: true },
          { key: 'site_id', label: 'Site', type: 'number' },
          { key: 'reported_by_id', label: 'Reported By', type: 'number' },
          { key: 'occurred_at', label: 'Occurred At', type: 'datetime' },
          { key: 'is_recordable', label: 'Recordable Case', type: 'boolean' },
          { key: 'is_lost_time', label: 'Lost Time Case', type: 'boolean' },
          { key: 'closure_requested', label: 'Closure Requested', type: 'boolean' },
          { key: 'closed_at', label: 'Closed At', type: 'datetime' },
          { key: 'closed_by_user_id', label: 'Closed By', type: 'number' },
        ],
      },
      {
        title: 'Description & Evidence',
        fields: [
          { key: 'description', label: 'Description', type: 'longtext', fullWidth: true },
          { key: 'attachments_metadata', label: 'Attachments', type: 'attachments', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'sios',
    label: 'Safety Improvement Observations',
    singular: 'SIO',
    route: '/sios',
    workflowForm: true,
    icon: ClipboardCheck,
    listEndpoint: '/sios',
    detailEndpoint: (id) => `/sios/${id}`,
    attachmentEntityType: 'sio',
    csvExportEndpoint: '/exports/sios.csv',
    description: 'Positive and negative safety observations with clear ownership and operational escalation.',
    filters: [
      { name: 'search', label: 'Search', type: 'search', placeholder: 'Description, category, person…' },
      { name: 'view', label: 'My views', type: 'select', options: ['assigned_to_me', 'reported_by_me', 'awaiting_my_verification', 'overdue_assigned_to_me'] },
      { name: 'site_id', label: 'Site', type: 'site' },
      { name: 'department_id', label: 'Originating department', type: 'department' },
      { name: 'responsible_department_id', label: 'Responsible department', type: 'department' },
      { name: 'responsible_user_id', label: 'Responsible user', type: 'user' },
      { name: 'source_type', label: 'Source', type: 'text' },
      { name: 'status', label: 'Status', type: 'select', options: ['open', 'unassigned', 'assigned', 'in_progress', 'pending_verification', 'complete', 'closed', 'no_action_required', 'reopened', 'assigned_to_responsible_person', 'assigned_to_action_tracker'] },
      { name: 'observation_nature', label: 'Nature', type: 'select', options: ['positive', 'negative'] },
      { name: 'urgency', label: 'Urgency', type: 'select', options: ['low', 'medium', 'high', 'urgent', 'not_applicable'] },
      { name: 'overdue', label: 'Overdue', type: 'select', options: ['true', 'false'] },
      { name: 'category', label: 'Category', type: 'text' },
      { name: 'incident_classification', label: 'Classification', type: 'text' },
      { name: 'date_from', label: 'From', type: 'date' },
      { name: 'date_to', label: 'To', type: 'date' },
      { name: 'source_created_from', label: 'Source created from', type: 'date' },
      { name: 'source_created_to', label: 'Source created to', type: 'date' },
    ],
    columns: [
      { key: 'reference_number', label: 'SIO Reference' },
      { key: 'external_reference_id', label: 'Source ID' },
      { key: 'observation_date', label: 'Date', render: (item) => renderDate(item, 'observation_date') },
      { key: 'source_type', label: 'Source' },
      { key: 'department', label: 'Department' },
      { key: 'responsible_department', label: 'Responsible Dept.' },
      { key: 'responsible_person_name', label: 'Responsible User' },
      { key: 'status', label: 'Status', render: (item) => renderBadge(item, 'status') },
      { key: 'observation_nature', label: 'Nature', render: (item) => renderBadge(item, 'observation_nature') },
      { key: 'urgency', label: 'Urgency', render: (item) => renderBadge(item, 'urgency') },
      { key: 'site_name', label: 'Site' },
      { key: 'due_date', label: 'Due', render: (item) => renderDate(item, 'due_date') },
      { key: 'age_days', label: 'Age', type: 'number' },
      { key: 'is_overdue', label: 'Aging', render: (item) => item.is_overdue ? `Overdue ${item.days_overdue}d` : 'On track' },
    ],
    detailSections: [
      {
        title: 'Observation Details',
        fields: [
          { key: 'reference_number', label: 'SIO Reference' },
          { key: 'external_reference_id', label: 'External Reference' },
          { key: 'observation_date', label: 'Observation Date', type: 'date' },
          { key: 'department', label: 'Department' },
          { key: 'source_type', label: 'Source Type' },
          { key: 'incident_classification', label: 'Incident Classification' },
          { key: 'category', label: 'Category' },
          { key: 'status', label: 'Status', badge: true },
          { key: 'observation_nature', label: 'Nature', badge: true },
          { key: 'urgency', label: 'Urgency', badge: true },
          { key: 'site_id', label: 'Site', type: 'number' },
          { key: 'description', label: 'Description', type: 'longtext', fullWidth: true },
          { key: 'property_damage', label: 'Property Damage' },
          { key: 'age_days', label: 'Age (days)', type: 'number' },
          { key: 'due_date', label: 'Due Date', type: 'date' },
          { key: 'days_overdue', label: 'Days Overdue', type: 'number' },
          { key: 'is_overdue', label: 'Overdue', type: 'boolean' },
        ],
      },
      {
        title: 'Responsibility',
        fields: [
          { key: 'responsible_department', label: 'Responsible Department' },
          { key: 'responsible_department_id', label: 'Responsible Department ID', type: 'number' },
          { key: 'assignment_status', label: 'Assignment Status', badge: true },
          { key: 'assigned_by_user_id', label: 'Assigned By', type: 'number' },
          { key: 'assigned_at', label: 'Assigned At', type: 'datetime' },
          { key: 'responsible_hs_officer_name', label: 'Responsible H&S Officer' },
          { key: 'responsible_hs_officer_user_id', label: 'Officer User', type: 'number' },
          { key: 'responsible_person_name', label: 'Responsible Person' },
          { key: 'responsible_person_user_id', label: 'Responsible Person User', type: 'number' },
          { key: 'responsible_user_id', label: 'Responsible User', type: 'number' },
          { key: 'assignment_decline_reason', label: 'Latest Decline Reason', type: 'longtext', fullWidth: true },
        ],
      },
      {
        title: 'Investigation & Closure',
        fields: [
          { key: 'investigation_required', label: 'Investigation Required', type: 'boolean' },
          { key: 'investigator_user_id', label: 'Investigator', type: 'number' },
          { key: 'investigation_started_at', label: 'Started At', type: 'datetime' },
          { key: 'investigation_completed_at', label: 'Completed At', type: 'datetime' },
          { key: 'root_cause', label: 'Root Cause', type: 'longtext', fullWidth: true },
          { key: 'investigation_summary', label: 'Investigation Summary', type: 'longtext', fullWidth: true },
          { key: 'lessons_learned', label: 'Lessons Learned', type: 'longtext', fullWidth: true },
          { key: 'closure_requested_at', label: 'Closure Requested', type: 'datetime' },
          { key: 'closure_notes', label: 'Closure Notes', type: 'longtext', fullWidth: true },
          { key: 'verified_by_user_id', label: 'Verified By', type: 'number' },
          { key: 'verified_at', label: 'Verified At', type: 'datetime' },
          { key: 'verification_notes', label: 'Verification Notes', type: 'longtext', fullWidth: true },
          { key: 'closed_at', label: 'Closed At', type: 'datetime' },
          { key: 'reopen_reason', label: 'Reopen Reason', type: 'longtext', fullWidth: true },
        ],
      },
      {
        title: 'Source Information',
        fields: [
          { key: 'source_system', label: 'Source System' },
          { key: 'source_created_at', label: 'Source Created At', type: 'datetime' },
          { key: 'source_created_by', label: 'Source Created By' },
          { key: 'source_modified_by', label: 'Source Modified By' },
          { key: 'source_path', label: 'Source Path', type: 'longtext', fullWidth: true },
          { key: 'legacy_metadata', label: 'Legacy Metadata', type: 'json', fullWidth: true },
          { key: 'created_by_user_id', label: 'Created By User', type: 'number' },
          { key: 'created_at', label: 'Created At', type: 'datetime' },
          { key: 'updated_at', label: 'Updated At', type: 'datetime' },
        ],
      },
    ],
  },
  {
    key: 'safety-kpis',
    label: 'Safety KPIs',
    singular: 'Safety KPI Record',
    route: '/safety-kpis',
    workflowForm: true,
    icon: Activity,
    listEndpoint: '/safety-kpis',
    detailEndpoint: (id) => `/safety-kpis/${id}`,
    description: 'Hours-worked periods with calculated TRIFR and LTIFR outputs.',
    columns: [
      { key: 'reporting_label', label: 'Label' },
      { key: 'site_id', label: 'Site', type: 'number' },
      { key: 'period_start', label: 'Period Start', render: (item) => renderDate(item, 'period_start') },
      { key: 'period_end', label: 'Period End', render: (item) => renderDate(item, 'period_end') },
      { key: 'hours_worked', label: 'Hours Worked', type: 'number' },
      { key: 'trifr', label: 'TRIFR', type: 'number' },
      { key: 'ltifr', label: 'LTIFR', type: 'number' },
    ],
    detailSections: [
      {
        title: 'KPI Period',
        fields: [
          { key: 'reporting_label', label: 'Reporting Label' },
          { key: 'site_id', label: 'Site', type: 'number' },
          { key: 'period_start', label: 'Period Start', type: 'date' },
          { key: 'period_end', label: 'Period End', type: 'date' },
          { key: 'hours_worked', label: 'Hours Worked', type: 'number' },
          { key: 'employees_count', label: 'Employees', type: 'number' },
          { key: 'contractors_count', label: 'Contractors', type: 'number' },
          { key: 'created_by_user_id', label: 'Created By', type: 'number' },
        ],
      },
      {
        title: 'Calculated Rates',
        fields: [
          { key: 'recordable_incidents', label: 'Recordable Incidents', type: 'number' },
          { key: 'lost_time_incidents', label: 'Lost Time Incidents', type: 'number' },
          { key: 'trifr', label: 'TRIFR', type: 'number' },
          { key: 'ltifr', label: 'LTIFR', type: 'number' },
          { key: 'notes', label: 'Notes', type: 'longtext', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'incident-investigations',
    label: 'Incident Investigations',
    singular: 'Incident Investigation',
    route: '/incident-investigations',
    workflowForm: true,
    icon: CheckSquare,
    attachmentEntityType: 'incident_investigation',
    listEndpoint: '/incident-investigations',
    detailEndpoint: (id) => `/incident-investigations/${id}`,
    description: 'Root cause investigations linked to incidents, including teams, witness statements, causes, and recommendations.',
    columns: [
      { key: 'incident_id', label: 'Incident', type: 'number' },
      { key: 'status', label: 'Status', render: (item) => renderBadge(item, 'status') },
      { key: 'site_id', label: 'Site', type: 'number' },
      { key: 'investigation_lead_user_id', label: 'Lead', type: 'number' },
      { key: 'target_completion_date', label: 'Target Completion', render: (item) => renderDate(item, 'target_completion_date') },
    ],
    detailSections: [
      {
        title: 'Investigation Summary',
        fields: [
          { key: 'incident_id', label: 'Incident', type: 'number' },
          { key: 'site_id', label: 'Site', type: 'number' },
          { key: 'status', label: 'Status', badge: true },
          { key: 'investigation_lead_user_id', label: 'Investigation Lead', type: 'number' },
          { key: 'approved_by_user_id', label: 'Approved By', type: 'number' },
          { key: 'target_completion_date', label: 'Target Completion Date', type: 'date' },
          { key: 'completed_at', label: 'Completed At', type: 'datetime' },
          { key: 'approved_at', label: 'Approved At', type: 'datetime' },
          { key: 'investigation_team', label: 'Investigation Team', type: 'list', fullWidth: true },
          { key: 'witness_statements', label: 'Witness Statements', type: 'object-list', fullWidth: true },
        ],
      },
      {
        title: 'Root Cause Analysis',
        fields: [
          { key: 'immediate_causes', label: 'Immediate Causes', type: 'list', fullWidth: true },
          { key: 'underlying_causes', label: 'Underlying Causes', type: 'list', fullWidth: true },
          { key: 'root_cause', label: 'Root Cause', type: 'longtext', fullWidth: true },
          { key: 'five_whys', label: 'Five Whys', type: 'list', fullWidth: true },
          { key: 'contributing_factors', label: 'Contributing Factors', type: 'list', fullWidth: true },
          { key: 'recommendations', label: 'Recommendations', type: 'list', fullWidth: true },
          { key: 'attachments_metadata', label: 'Attachments', type: 'attachments', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'legal-compliance',
    label: 'Legal Compliance',
    singular: 'Legal Compliance Item',
    route: '/legal-compliance',
    workflowForm: true,
    icon: FileCheck2,
    attachmentEntityType: 'legal_compliance',
    listEndpoint: '/legal-compliance',
    detailEndpoint: (id) => `/legal-compliance/${id}`,
    description: 'Regulatory obligations with ownership, review cadence, evidence needs, and compliance status.',
    columns: [
      { key: 'title', label: 'Title' },
      { key: 'compliance_status', label: 'Status', render: (item) => renderBadge(item, 'compliance_status') },
      { key: 'regulatory_body', label: 'Regulator' },
      { key: 'owner_user_id', label: 'Owner', type: 'number' },
      { key: 'next_review_date', label: 'Next Review', render: (item) => renderDate(item, 'next_review_date') },
    ],
    detailSections: [
      {
        title: 'Register Item',
        fields: [
          { key: 'title', label: 'Title' },
          { key: 'compliance_status', label: 'Compliance Status', badge: true },
          { key: 'regulatory_body', label: 'Regulatory Body' },
          { key: 'legal_reference', label: 'Legal Reference' },
          { key: 'site_id', label: 'Site', type: 'number' },
          { key: 'owner_user_id', label: 'Owner', type: 'number' },
          { key: 'review_frequency', label: 'Review Frequency' },
          { key: 'next_review_date', label: 'Next Review Date', type: 'date' },
          { key: 'last_reviewed_at', label: 'Last Reviewed At', type: 'datetime' },
          { key: 'evidence_required', label: 'Evidence Required', type: 'boolean' },
        ],
      },
      {
        title: 'Requirement & Evidence',
        fields: [
          { key: 'requirement_summary', label: 'Requirement Summary', type: 'longtext', fullWidth: true },
          { key: 'notes', label: 'Notes', type: 'longtext', fullWidth: true },
          { key: 'attachments_metadata', label: 'Attachments', type: 'attachments', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'jsas',
    label: 'JSA / Risk Assessments',
    singular: 'JSA',
    route: '/jsas',
    workflowForm: true,
    icon: ClipboardCheck,
    attachmentEntityType: 'jsa',
    listEndpoint: '/jsas',
    detailEndpoint: (id) => `/jsas/${id}`,
    description: 'Job safety analyses and risk assessments that require approval before operational use.',
    columns: [
      { key: 'title', label: 'Title' },
      { key: 'status', label: 'Status', render: (item) => renderBadge(item, 'status') },
      { key: 'residual_risk_level', label: 'Residual Risk', render: (item) => renderBadge(item, 'residual_risk_level') },
      { key: 'site_id', label: 'Site', type: 'number' },
      { key: 'review_date', label: 'Review Date', render: (item) => renderDate(item, 'review_date') },
    ],
    detailSections: [
      {
        title: 'Assessment Summary',
        fields: [
          { key: 'title', label: 'Title' },
          { key: 'status', label: 'Status', badge: true },
          { key: 'site_id', label: 'Site', type: 'number' },
          { key: 'department_or_area', label: 'Department / Area' },
          { key: 'residual_risk_level', label: 'Residual Risk Level', badge: true },
          { key: 'review_date', label: 'Review Date', type: 'date' },
          { key: 'approved_by_user_id', label: 'Approved By', type: 'number' },
          { key: 'approved_at', label: 'Approved At', type: 'datetime' },
        ],
      },
      {
        title: 'Steps, Hazards, and Controls',
        fields: [
          { key: 'job_steps', label: 'Job Steps', type: 'list', fullWidth: true },
          { key: 'hazards', label: 'Hazards', type: 'list', fullWidth: true },
          { key: 'controls', label: 'Controls', type: 'list', fullWidth: true },
          { key: 'ppe_required', label: 'PPE Required', type: 'list', fullWidth: true },
          { key: 'attachments_metadata', label: 'Attachments', type: 'attachments', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'contractors',
    label: 'Contractors',
    singular: 'Contractor',
    route: '/contractors',
    workflowForm: true,
    icon: Users,
    attachmentEntityType: 'contractor',
    listEndpoint: '/contractors',
    detailEndpoint: (id) => `/contractors/${id}`,
    description: 'Contractor onboarding, induction, insurance, and document compliance records for work approval.',
    columns: [
      { key: 'contractor_name', label: 'Contractor' },
      { key: 'approved_for_work', label: 'Approved', render: (item) => <Badge value={item.approved_for_work ? 'approved' : 'blocked'} /> },
      { key: 'onboarding_status', label: 'Onboarding', render: (item) => renderBadge(item, 'onboarding_status') },
      { key: 'induction_status', label: 'Induction', render: (item) => renderBadge(item, 'induction_status') },
      { key: 'insurance_expiry_date', label: 'Insurance Expiry', render: (item) => renderDate(item, 'insurance_expiry_date') },
    ],
    detailSections: [
      {
        title: 'Contractor Profile',
        fields: [
          { key: 'contractor_name', label: 'Contractor Name' },
          { key: 'contact_person', label: 'Contact Person' },
          { key: 'contact_email', label: 'Contact Email' },
          { key: 'contact_phone', label: 'Contact Phone' },
          { key: 'site_id', label: 'Site', type: 'number' },
          { key: 'approved_for_work', label: 'Approved For Work', type: 'boolean' },
          { key: 'onboarding_status', label: 'Onboarding Status', badge: true },
          { key: 'induction_status', label: 'Induction Status', badge: true },
          { key: 'compliance_documents_status', label: 'Compliance Documents Status', badge: true },
          { key: 'insurance_expiry_date', label: 'Insurance Expiry Date', type: 'date' },
          { key: 'documents_expiry_date', label: 'Documents Expiry Date', type: 'date' },
        ],
      },
      {
        title: 'Scope & Evidence',
        fields: [
          { key: 'work_scope', label: 'Work Scope', type: 'longtext', fullWidth: true },
          { key: 'notes', label: 'Notes', type: 'longtext', fullWidth: true },
          { key: 'attachments_metadata', label: 'Attachments', type: 'attachments', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'asset-register',
    label: 'Equipment / PPE Register',
    singular: 'Asset',
    route: '/asset-register',
    workflowForm: true,
    icon: Wrench,
    attachmentEntityType: 'asset_register',
    listEndpoint: '/asset-register',
    detailEndpoint: (id) => `/asset-register/${id}`,
    description: 'Equipment, PPE, and emergency asset records with inspection cadence, assignment, and condition status.',
    columns: [
      { key: 'asset_name', label: 'Asset Name' },
      { key: 'asset_type', label: 'Asset Type', render: (item) => renderBadge(item, 'asset_type') },
      { key: 'condition_status', label: 'Condition', render: (item) => renderBadge(item, 'condition_status') },
      { key: 'site_id', label: 'Site', type: 'number' },
      { key: 'next_inspection_date', label: 'Next Inspection', render: (item) => renderDate(item, 'next_inspection_date') },
    ],
    detailSections: [
      {
        title: 'Asset Profile',
        fields: [
          { key: 'asset_name', label: 'Asset Name' },
          { key: 'asset_type', label: 'Asset Type', badge: true },
          { key: 'asset_tag', label: 'Asset Tag' },
          { key: 'site_id', label: 'Site', type: 'number' },
          { key: 'location', label: 'Location' },
          { key: 'assigned_to_user_id', label: 'Assigned To', type: 'number' },
          { key: 'inspection_frequency', label: 'Inspection Frequency' },
          { key: 'next_inspection_date', label: 'Next Inspection Date', type: 'date' },
          { key: 'condition_status', label: 'Condition Status', badge: true },
          { key: 'last_inspected_at', label: 'Last Inspected At', type: 'datetime' },
        ],
      },
      {
        title: 'Notes & Evidence',
        fields: [
          { key: 'notes', label: 'Notes', type: 'longtext', fullWidth: true },
          { key: 'attachments_metadata', label: 'Attachments', type: 'attachments', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'medical-surveillance',
    label: 'Occupational Health',
    singular: 'Medical Surveillance Record',
    route: '/medical-surveillance',
    customPage: true,
    icon: Activity,
    attachmentEntityType: 'medical_surveillance',
    listEndpoint: '/medical-surveillance',
    detailEndpoint: (id) => `/medical-surveillance/${id}`,
    description: 'Exposure-linked surveillance, fitness, appointments, restrictions, illness cases, and compliance.',
    columns: [
      { key: 'employee_user_id', label: 'Employee', type: 'number' },
      { key: 'surveillance_type', label: 'Type' },
      { key: 'status', label: 'Status', render: (item) => renderBadge(item, 'status') },
      { key: 'medical_clearance_status', label: 'Clearance', render: (item) => renderBadge(item, 'medical_clearance_status') },
      { key: 'due_date', label: 'Due Date', render: (item) => renderDate(item, 'due_date') },
    ],
    detailSections: [
      {
        title: 'Surveillance Profile',
        fields: [
          { key: 'employee_user_id', label: 'Employee User', type: 'number' },
          { key: 'site_id', label: 'Site', type: 'number' },
          { key: 'surveillance_type', label: 'Surveillance Type' },
          { key: 'status', label: 'Status', badge: true },
          { key: 'medical_clearance_status', label: 'Medical Clearance', badge: true },
          { key: 'due_date', label: 'Due Date', type: 'date' },
          { key: 'completed_at', label: 'Completed At', type: 'datetime' },
          { key: 'next_due_date', label: 'Next Due Date', type: 'date' },
        ],
      },
      {
        title: 'Results & Evidence',
        fields: [
          { key: 'results_summary', label: 'Results Summary', type: 'longtext', fullWidth: true },
          { key: 'notes', label: 'Notes', type: 'longtext', fullWidth: true },
          { key: 'attachments_metadata', label: 'Attachments', type: 'attachments', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'emergency-drills',
    label: 'Emergency Drills',
    singular: 'Emergency Drill',
    route: '/emergency-drills',
    workflowForm: true,
    icon: Siren,
    attachmentEntityType: 'emergency_drill',
    listEndpoint: '/emergency-drills',
    detailEndpoint: (id) => `/emergency-drills/${id}`,
    description: 'Emergency drill scheduling, attendance tracking, and post-drill evaluations.',
    columns: [
      { key: 'emergency_type', label: 'Type' },
      { key: 'site_id', label: 'Site', type: 'number' },
      { key: 'status', label: 'Status', render: (item) => renderBadge(item, 'status') },
      { key: 'drill_date', label: 'Drill Date', render: (item) => renderDate(item, 'drill_date') },
      { key: 'next_drill_date', label: 'Next Drill', render: (item) => renderDate(item, 'next_drill_date') },
    ],
    detailSections: [
      {
        title: 'Drill Schedule',
        fields: [
          { key: 'emergency_type', label: 'Emergency Type' },
          { key: 'site_id', label: 'Site', type: 'number' },
          { key: 'status', label: 'Status', badge: true },
          { key: 'drill_date', label: 'Drill Date', type: 'date' },
          { key: 'next_drill_date', label: 'Next Drill Date', type: 'date' },
          { key: 'participants', label: 'Participants', type: 'list', fullWidth: true },
          { key: 'attendance_records', label: 'Attendance', type: 'object-list', fullWidth: true },
        ],
      },
      {
        title: 'Evaluation',
        fields: [
          { key: 'outcome', label: 'Outcome', type: 'longtext', fullWidth: true },
          { key: 'issues_found', label: 'Issues Found', type: 'list', fullWidth: true },
          { key: 'corrective_actions', label: 'Corrective Actions', type: 'list', fullWidth: true },
          { key: 'attachments_metadata', label: 'Attachments', type: 'attachments', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'documents',
    label: 'Document Control',
    singular: 'Document',
    route: '/documents',
    workflowForm: true,
    icon: FileCheck2,
    attachmentEntityType: 'document_control',
    approvalConfig: {
      entityType: 'document_control',
      actionType: 'document_approval',
      requestLabel: 'Request document approval',
      requestTitle: 'Request Controlled Document Approval',
    },
    listEndpoint: '/documents',
    detailEndpoint: (id) => `/documents/${id}`,
    description: 'Controlled policies, SOPs, procedures, and forms with versioning and approval workflow.',
    columns: [
      { key: 'title', label: 'Title' },
      { key: 'document_type', label: 'Type', render: (item) => renderBadge(item, 'document_type') },
      { key: 'version', label: 'Version' },
      { key: 'status', label: 'Status', render: (item) => renderBadge(item, 'status') },
      { key: 'expiry_date', label: 'Expiry Date', render: (item) => renderDate(item, 'expiry_date') },
    ],
    detailSections: [
      {
        title: 'Document Profile',
        fields: [
          { key: 'title', label: 'Title' },
          { key: 'document_type', label: 'Document Type', badge: true },
          { key: 'version', label: 'Version' },
          { key: 'site_id', label: 'Site', type: 'number' },
          { key: 'status', label: 'Status', badge: true },
          { key: 'created_by_user_id', label: 'Created By', type: 'number' },
          { key: 'approved_by_user_id', label: 'Approved By', type: 'number' },
          { key: 'approved_at', label: 'Approved At', type: 'datetime' },
          { key: 'expiry_date', label: 'Expiry Date', type: 'date' },
          { key: 'supersedes_document_id', label: 'Supersedes Document', type: 'number' },
        ],
      },
      {
        title: 'Acknowledgements & Files',
        fields: [
          { key: 'acknowledgement_required', label: 'Acknowledgement Required', type: 'boolean' },
          { key: 'acknowledgement_user_ids', label: 'Acknowledgement Users', type: 'list', fullWidth: true },
          { key: 'attachments_metadata', label: 'Attachments', type: 'attachments', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'audits',
    label: 'Audits',
    singular: 'Audit',
    route: '/audits',
    workflowForm: true,
    icon: ClipboardCheck,
    attachmentEntityType: 'audit_management',
    listEndpoint: '/audits',
    detailEndpoint: (id) => `/audits/${id}`,
    description: 'Internal, external, and compliance audits with findings, recommendations, and scoring.',
    columns: [
      { key: 'audit_type', label: 'Type', render: (item) => renderBadge(item, 'audit_type') },
      { key: 'site_id', label: 'Site', type: 'number' },
      { key: 'status', label: 'Status', render: (item) => renderBadge(item, 'status') },
      { key: 'audit_date', label: 'Audit Date', render: (item) => renderDate(item, 'audit_date') },
      { key: 'audit_score', label: 'Score', type: 'number' },
    ],
    detailSections: [
      {
        title: 'Audit Overview',
        fields: [
          { key: 'audit_type', label: 'Audit Type', badge: true },
          { key: 'site_id', label: 'Site', type: 'number' },
          { key: 'auditor_user_id', label: 'Auditor', type: 'number' },
          { key: 'audit_date', label: 'Audit Date', type: 'date' },
          { key: 'status', label: 'Status', badge: true },
          { key: 'audit_score', label: 'Audit Score', type: 'number' },
        ],
      },
      {
        title: 'Findings & Evidence',
        fields: [
          { key: 'findings', label: 'Findings', type: 'list', fullWidth: true },
          { key: 'non_conformances', label: 'Non-Conformances', type: 'list', fullWidth: true },
          { key: 'recommendations', label: 'Recommendations', type: 'list', fullWidth: true },
          { key: 'corrective_action_ids', label: 'Corrective Action IDs', type: 'list', fullWidth: true },
          { key: 'attachments_metadata', label: 'Attachments', type: 'attachments', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'notification-deliveries',
    label: 'Notification Deliveries',
    singular: 'Delivery Log',
    route: '/notification-deliveries',
    icon: Bell,
    listEndpoint: '/notification-deliveries',
    detailEndpoint: (id) => `/notification-deliveries/${id}`,
    description: 'Email and SMS delivery attempts produced from workflow notifications.',
    columns: [
      { key: 'notification_id', label: 'Notification', type: 'number' },
      { key: 'recipient_user_id', label: 'Recipient', type: 'number' },
      { key: 'channel', label: 'Channel', render: (item) => renderBadge(item, 'channel') },
      { key: 'status', label: 'Status', render: (item) => renderBadge(item, 'status') },
      { key: 'sent_at', label: 'Sent At', render: (item) => renderDateTime(item, 'sent_at') },
    ],
    detailSections: [
      {
        title: 'Delivery Record',
        fields: [
          { key: 'notification_id', label: 'Notification ID', type: 'number' },
          { key: 'recipient_user_id', label: 'Recipient User', type: 'number' },
          { key: 'channel', label: 'Channel', badge: true },
          { key: 'destination', label: 'Destination' },
          { key: 'provider', label: 'Provider' },
          { key: 'status', label: 'Status', badge: true },
          { key: 'sent_at', label: 'Sent At', type: 'datetime' },
          { key: 'error_message', label: 'Error Message', type: 'longtext', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'job-runs',
    label: 'Job Runs',
    singular: 'Job Run',
    route: '/job-runs',
    icon: History,
    listEndpoint: '/job-runs',
    detailEndpoint: (id) => `/job-runs/${id}`,
    description: 'Background scheduler run history, outcomes, and processing counts.',
    columns: [
      { key: 'job_name', label: 'Job Name' },
      { key: 'status', label: 'Status', render: (item) => renderBadge(item, 'status') },
      { key: 'records_processed', label: 'Processed', type: 'number' },
      { key: 'started_at', label: 'Started', render: (item) => renderDateTime(item, 'started_at') },
      { key: 'completed_at', label: 'Completed', render: (item) => renderDateTime(item, 'completed_at') },
    ],
    detailSections: [
      {
        title: 'Job Run',
        fields: [
          { key: 'job_name', label: 'Job Name' },
          { key: 'status', label: 'Status', badge: true },
          { key: 'records_processed', label: 'Records Processed', type: 'number' },
          { key: 'started_at', label: 'Started At', type: 'datetime' },
          { key: 'completed_at', label: 'Completed At', type: 'datetime' },
          { key: 'details', label: 'Details', type: 'json', fullWidth: true },
          { key: 'error_message', label: 'Error Message', type: 'longtext', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'safety-communications',
    label: 'Safety Communications',
    singular: 'Safety Communication',
    route: '/safety-communications',
    workflowForm: true,
    icon: Megaphone,
    attachmentEntityType: 'safety_communication',
    listEndpoint: '/safety-communications',
    detailEndpoint: (id) => `/safety-communications/${id}`,
    description: 'Toolbox talks, safety alerts, posters, signage, and campaigns distributed to sites.',
    columns: [
      { key: 'title', label: 'Title' },
      { key: 'communication_type', label: 'Type', render: (item) => renderBadge(item, 'communication_type') },
      { key: 'status', label: 'Status', render: (item) => renderBadge(item, 'status') },
      { key: 'site_id', label: 'Site', type: 'number' },
      { key: 'issued_at', label: 'Issued', render: (item) => renderDateTime(item, 'issued_at') },
    ],
    detailSections: [
      {
        title: 'Communication Summary',
        fields: [
          { key: 'title', label: 'Title' },
          { key: 'communication_type', label: 'Type', badge: true },
          { key: 'status', label: 'Status', badge: true },
          { key: 'site_id', label: 'Site', type: 'number' },
          { key: 'owner_user_id', label: 'Owner', type: 'number' },
          { key: 'audience', label: 'Audience' },
          { key: 'requires_acknowledgement', label: 'Requires Acknowledgement', type: 'boolean' },
          { key: 'issued_at', label: 'Issued At', type: 'datetime' },
          { key: 'expires_at', label: 'Expires At', type: 'datetime' },
        ],
      },
      {
        title: 'Message & Evidence',
        fields: [
          { key: 'summary', label: 'Summary', type: 'longtext', fullWidth: true },
          { key: 'details', label: 'Details', type: 'longtext', fullWidth: true },
          { key: 'attachments_metadata', label: 'Attachments', type: 'attachments', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'behaviour-observations',
    label: 'Behaviour Observations',
    singular: 'Behaviour Observation',
    route: '/behaviour-observations',
    workflowForm: true,
    icon: Eye,
    attachmentEntityType: 'behaviour_observation',
    listEndpoint: '/behaviour-observations',
    detailEndpoint: (id) => `/behaviour-observations/${id}`,
    description: 'Unsafe acts, positive observations, conduct issues, and event safety observations.',
    columns: [
      { key: 'title', label: 'Title' },
      { key: 'observation_type', label: 'Type', render: (item) => renderBadge(item, 'observation_type') },
      { key: 'status', label: 'Status', render: (item) => renderBadge(item, 'status') },
      { key: 'severity', label: 'Severity', render: (item) => renderBadge(item, 'severity') },
      { key: 'observed_at', label: 'Observed', render: (item) => renderDateTime(item, 'observed_at') },
    ],
    detailSections: [
      {
        title: 'Observation Summary',
        fields: [
          { key: 'title', label: 'Title' },
          { key: 'observation_type', label: 'Observation Type', badge: true },
          { key: 'status', label: 'Status', badge: true },
          { key: 'severity', label: 'Severity', badge: true },
          { key: 'site_id', label: 'Site', type: 'number' },
          { key: 'observed_by_user_id', label: 'Observed By', type: 'number' },
          { key: 'person_involved_name', label: 'Person / Team' },
          { key: 'action_required', label: 'Action Required', type: 'boolean' },
          { key: 'observed_at', label: 'Observed At', type: 'datetime' },
          { key: 'closed_at', label: 'Closed At', type: 'datetime' },
          { key: 'closed_by_user_id', label: 'Closed By', type: 'number' },
        ],
      },
      {
        title: 'Follow-up & Evidence',
        fields: [
          { key: 'description', label: 'Description', type: 'longtext', fullWidth: true },
          { key: 'immediate_action_taken', label: 'Immediate Action Taken', type: 'longtext', fullWidth: true },
          { key: 'follow_up_notes', label: 'Follow-up Notes', type: 'longtext', fullWidth: true },
          { key: 'attachments_metadata', label: 'Attachments', type: 'attachments', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'hazards',
    label: 'Hazards',
    singular: 'Hazard',
    route: '/hazards',
    workflowForm: true,
    icon: ShieldAlert,
    attachmentEntityType: 'hazard',
    approvalConfig: {
      entityType: 'hazard',
      actionType: 'hazard_review',
      requestLabel: 'Request hazard review',
      requestTitle: 'Request High or Critical Hazard Review',
    },
    listEndpoint: '/hazards',
    detailEndpoint: (id) => `/hazards/${id}`,
    description: 'Risk register entries with scores, controls, and linked incidents.',
    columns: [
      { key: 'title', label: 'Title' },
      { key: 'risk_level', label: 'Risk Level', render: (item) => renderBadge(item, 'risk_level') },
      { key: 'status', label: 'Status', render: (item) => renderBadge(item, 'status') },
      { key: 'risk_score', label: 'Score', type: 'number' },
      { key: 'review_date', label: 'Review Date', render: (item) => renderDate(item, 'review_date') },
    ],
    detailSections: [
      {
        title: 'Risk Summary',
        fields: [
          { key: 'title', label: 'Title' },
          { key: 'status', label: 'Status', badge: true },
          { key: 'risk_level', label: 'Risk Level', badge: true },
          { key: 'risk_score', label: 'Risk Score', type: 'number' },
          { key: 'likelihood', label: 'Likelihood', type: 'number' },
          { key: 'impact', label: 'Impact', type: 'number' },
        ],
      },
      {
        title: 'Ownership & Controls',
        fields: [
          { key: 'owner_user_id', label: 'Owner User', type: 'number' },
          { key: 'site_id', label: 'Site', type: 'number' },
          { key: 'incident_id', label: 'Linked Incident', type: 'number' },
          { key: 'due_date', label: 'Due Date', type: 'date' },
          { key: 'review_date', label: 'Review Date', type: 'date' },
          { key: 'reviewed_at', label: 'Reviewed At', type: 'datetime' },
          { key: 'reviewed_by_user_id', label: 'Reviewed By', type: 'number' },
          { key: 'existing_controls', label: 'Existing Controls', type: 'list', fullWidth: true },
          { key: 'additional_controls', label: 'Additional Controls', type: 'list', fullWidth: true },
          { key: 'description', label: 'Description', type: 'longtext', fullWidth: true },
          { key: 'attachments_metadata', label: 'Attachments', type: 'attachments', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'inspections',
    label: 'Inspections',
    singular: 'Inspection',
    route: '/inspections',
    workflowForm: true,
    icon: ClipboardCheck,
    attachmentEntityType: 'inspection',
    listEndpoint: '/inspections',
    detailEndpoint: (id) => `/inspections/${id}`,
    description: 'Inspection activity with checklist outcomes and linked hazards.',
    columns: [
      { key: 'title', label: 'Title' },
      { key: 'status', label: 'Status', render: (item) => renderBadge(item, 'status') },
      { key: 'overall_result', label: 'Result', render: (item) => renderBadge(item, 'overall_result') },
      { key: 'inspection_type', label: 'Type' },
      { key: 'inspection_date', label: 'Date', render: (item) => renderDateTime(item, 'inspection_date') },
    ],
    detailSections: [
      {
        title: 'Inspection Overview',
        fields: [
          { key: 'title', label: 'Title' },
          { key: 'status', label: 'Status', badge: true },
          { key: 'overall_result', label: 'Overall Result', badge: true },
          { key: 'inspection_type', label: 'Inspection Type' },
          { key: 'area_location', label: 'Area / Location' },
          { key: 'inspection_date', label: 'Inspection Date', type: 'datetime' },
          { key: 'inspector_user_id', label: 'Inspector User', type: 'number' },
          { key: 'site_id', label: 'Site', type: 'number' },
          { key: 'number_of_non_conformities', label: 'Non-conformities', type: 'number' },
          { key: 'number_of_observations', label: 'Observations', type: 'number' },
        ],
      },
      {
        title: 'Findings & Checklist',
        fields: [
          { key: 'notes', label: 'Notes', type: 'longtext', fullWidth: true },
          { key: 'findings_summary', label: 'Findings Summary', type: 'longtext', fullWidth: true },
          { key: 'linked_hazard_ids', label: 'Linked Hazards', type: 'list', fullWidth: true },
          { key: 'checklist_items', label: 'Checklist Items', type: 'object-list', fullWidth: true },
          { key: 'attachments_metadata', label: 'Attachments', type: 'attachments', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'corrective-actions',
    label: 'Action Centre',
    singular: 'Action',
    route: '/corrective-actions',
    workflowForm: true,
    customPage: true,
    icon: Wrench,
    attachmentEntityType: 'corrective_action',
    listEndpoint: '/corrective-actions',
    detailEndpoint: (id) => `/corrective-actions/${id}`,
    description: 'The unified register for HSE and compliance actions across every source module.',
    filters: [
      { name: 'search', label: 'Search', type: 'search' },
      { name: 'site_id', label: 'Site', type: 'site' },
      { name: 'department_id', label: 'Department', type: 'department' },
      { name: 'responsible_department_id', label: 'Responsible department', type: 'department' },
      { name: 'assigned_to_user_id', label: 'Owner', type: 'user' },
      { name: 'assigned_by_user_id', label: 'Assigner', type: 'user' },
      { name: 'verifier_user_id', label: 'Verifier', type: 'user' },
      { name: 'source_type', label: 'Source', type: 'select', options: ['manual', 'sio', 'incident', 'hazard', 'inspection', 'audit', 'permit', 'jsa', 'training', 'compliance', 'contractor', 'emergency_drill', 'document_control', 'ppe', 'fleet', 'environmental', 'management_of_change'] },
      { name: 'priority', label: 'Priority', type: 'select', options: ['low', 'medium', 'high', 'critical'] },
      { name: 'status', label: 'Lifecycle', type: 'select', options: ['draft', 'open', 'assigned', 'accepted', 'in_progress', 'completion_requested', 'pending_verification', 'declined', 'on_hold', 'closed', 'reopened', 'cancelled'] },
      { name: 'overdue', label: 'Overdue', type: 'select', options: ['true', 'false'] },
      { name: 'due_soon_days', label: 'Due within', type: 'select', options: ['7', '30'] },
      { name: 'date_from', label: 'Due from', type: 'date' },
      { name: 'date_to', label: 'Due to', type: 'date' },
      { name: 'age_bucket', label: 'Age bucket', type: 'select', options: ['0-7', '8-30', '31-60', '61-90', '90+'] },
      { name: 'extension_count', label: 'Min. extensions', type: 'number' },
      { name: 'reopened', label: 'Reopened', type: 'select', options: ['true', 'false'] },
      { name: 'awaiting_verification', label: 'Awaiting verification', type: 'select', options: ['true', 'false'] },
    ],
    columns: [
      { key: 'action_reference', label: 'Action Ref' },
      { key: 'title', label: 'Title' },
      { key: 'source_type', label: 'Source' },
      { key: 'site_name', label: 'Site' },
      { key: 'department_name', label: 'Department' },
      { key: 'responsible_department_name', label: 'Responsible Department' },
      { key: 'owner_name', label: 'Owner' },
      { key: 'priority', label: 'Priority', render: (item) => renderBadge(item, 'priority') },
      { key: 'lifecycle_status', label: 'Status', render: (item) => <Badge value={item.lifecycle_status} /> },
      { key: 'progress_percent', label: 'Progress', render: (item) => `${item.progress_percent}%` },
      { key: 'original_due_date', label: 'Original Due', render: (item) => renderDate(item, 'original_due_date') },
      { key: 'current_due_date', label: 'Current Due', render: (item) => renderDate(item, 'current_due_date') },
      { key: 'age_days', label: 'Age', render: (item) => `${item.age_days}d` },
      { key: 'is_overdue', label: 'Overdue', render: (item) => item.is_overdue ? `${item.days_overdue}d` : 'No' },
      { key: 'awaiting_verification', label: 'Verification', render: (item) => item.awaiting_verification ? 'Awaiting' : '—' },
    ],
    detailSections: [
      {
        title: 'Action Overview',
        fields: [
          { key: 'action_reference', label: 'Action Reference' },
          { key: 'title', label: 'Title' },
          { key: 'lifecycle_status', label: 'Lifecycle Status', badge: true },
          { key: 'priority', label: 'Priority', badge: true },
          { key: 'source_type', label: 'Source Type' },
          { key: 'source_id', label: 'Source Record', type: 'number' },
          { key: 'site_id', label: 'Site', type: 'number' },
          { key: 'owner_name', label: 'Accountable Owner' },
          { key: 'assigned_by_name', label: 'Assigning Manager' },
          { key: 'verifier_name', label: 'Verifier' },
          { key: 'department_name', label: 'Department' },
          { key: 'responsible_department_name', label: 'Responsible Department' },
          { key: 'created_by_user_id', label: 'Created By', type: 'number' },
          { key: 'verified_by_user_id', label: 'Verified By', type: 'number' },
          { key: 'original_due_date', label: 'Original Due Date', type: 'date' },
          { key: 'current_due_date', label: 'Current Due Date', type: 'date' },
          { key: 'progress_percent', label: 'Progress', type: 'number' },
          { key: 'started_at', label: 'Started At', type: 'datetime' },
          { key: 'completed_at', label: 'Completed At', type: 'datetime' },
          { key: 'verified_at', label: 'Verified At', type: 'datetime' },
        ],
      },
      {
        title: 'Outcome, Closure & Verification',
        fields: [
          { key: 'description', label: 'Description', type: 'longtext', fullWidth: true },
          { key: 'acceptance_criteria', label: 'Acceptance Criteria', type: 'longtext', fullWidth: true },
          { key: 'progress_notes', label: 'Progress Notes', type: 'longtext', fullWidth: true },
          { key: 'completion_notes', label: 'Completion Notes', type: 'longtext', fullWidth: true },
          { key: 'verification_notes', label: 'Verification Notes', type: 'longtext', fullWidth: true },
          { key: 'closure_evidence_metadata', label: 'Closure Evidence', type: 'attachments', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'approvals',
    label: 'Approvals',
    singular: 'Approval',
    route: '/approvals',
    icon: CheckSquare,
    listEndpoint: '/approvals',
    detailEndpoint: (id) => `/approvals/${id}`,
    description: 'Formal review requests and decisions for high-value OHS workflows.',
    columns: [
      { key: 'action_type', label: 'Action Type' },
      { key: 'entity_type', label: 'Entity Type' },
      { key: 'entity_id', label: 'Entity Id', type: 'number' },
      { key: 'status', label: 'Status', render: (item) => renderBadge(item, 'status') },
      { key: 'requested_by_user_id', label: 'Requested By', type: 'number' },
      { key: 'created_at', label: 'Created', render: (item) => renderDateTime(item, 'created_at') },
    ],
    detailSections: [
      {
        title: 'Approval Summary',
        fields: [
          { key: 'action_type', label: 'Action Type' },
          { key: 'entity_type', label: 'Entity Type' },
          { key: 'entity_id', label: 'Entity Id', type: 'number' },
          { key: 'status', label: 'Status', badge: true },
          { key: 'requested_by_user_id', label: 'Requested By', type: 'number' },
          { key: 'assigned_approver_user_id', label: 'Assigned Approver', type: 'number' },
          { key: 'decided_by_user_id', label: 'Decided By', type: 'number' },
          { key: 'decided_at', label: 'Decided At', type: 'datetime' },
          { key: 'created_at', label: 'Created At', type: 'datetime' },
          { key: 'updated_at', label: 'Updated At', type: 'datetime' },
        ],
      },
      {
        title: 'Workflow Notes',
        fields: [
          { key: 'request_notes', label: 'Request Notes', type: 'longtext', fullWidth: true },
          { key: 'decision_notes', label: 'Decision Notes', type: 'longtext', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'notifications',
    label: 'Notifications',
    singular: 'Notification',
    route: '/notifications',
    icon: Bell,
    listEndpoint: '/notifications',
    detailEndpoint: (id) => `/notifications/${id}`,
    description: 'User notifications driven by critical events and reminder workflows.',
    columns: [
      { key: 'title', label: 'Title' },
      { key: 'notification_type', label: 'Type' },
      { key: 'severity', label: 'Severity', render: (item) => renderBadge(item, 'severity') },
      {
        key: 'is_read',
        label: 'Read',
        render: (item) => <Badge value={item.is_read ? 'read' : 'unread'} />,
      },
      { key: 'created_at', label: 'Created', render: (item) => renderDateTime(item, 'created_at') },
    ],
    detailSections: [
      {
        title: 'Notification',
        fields: [
          { key: 'title', label: 'Title' },
          { key: 'notification_type', label: 'Notification Type' },
          { key: 'severity', label: 'Severity', badge: true },
          { key: 'related_entity_type', label: 'Related Entity Type' },
          { key: 'related_entity_id', label: 'Related Entity Id', type: 'number' },
          { key: 'recipient_user_id', label: 'Recipient User', type: 'number' },
          { key: 'is_read', label: 'Read', type: 'boolean' },
          { key: 'read_at', label: 'Read At', type: 'datetime' },
          { key: 'created_at', label: 'Created At', type: 'datetime' },
          { key: 'message', label: 'Message', type: 'longtext', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'training',
    label: 'Training & Competency',
    singular: 'Training Record',
    route: '/training',
    icon: GraduationCap,
    attachmentEntityType: 'training',
    listEndpoint: '/training',
    detailEndpoint: (id) => `/training/${id}`,
    description: 'Enterprise training, competency, certification, authorization, and explainable work eligibility.',
    customPage: true,
    columns: [
      { key: 'title', label: 'Title' },
      { key: 'training_type', label: 'Training Type' },
      { key: 'status', label: 'Status', render: (item) => renderBadge(item, 'status') },
      { key: 'assigned_to_user_id', label: 'Assigned To', type: 'number' },
      { key: 'due_date', label: 'Due Date', render: (item) => renderDate(item, 'due_date') },
    ],
    detailSections: [
      {
        title: 'Training Summary',
        fields: [
          { key: 'title', label: 'Title' },
          { key: 'training_type', label: 'Training Type' },
          { key: 'status', label: 'Status', badge: true },
          { key: 'site_id', label: 'Site', type: 'number' },
          { key: 'assigned_to_user_id', label: 'Assigned To', type: 'number' },
          { key: 'assigned_by_user_id', label: 'Assigned By', type: 'number' },
          { key: 'due_date', label: 'Due Date', type: 'date' },
          { key: 'completed_at', label: 'Completed At', type: 'datetime' },
          { key: 'expiry_date', label: 'Expiry Date', type: 'date' },
          { key: 'certificate_metadata', label: 'Certificate', type: 'attachments', fullWidth: true },
          { key: 'notes', label: 'Notes', type: 'longtext', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'compliance-acknowledgements',
    label: 'Compliance Acknowledgements',
    singular: 'Compliance Acknowledgement',
    route: '/compliance-acknowledgements',
    icon: FileCheck2,
    attachmentEntityType: 'compliance_acknowledgement',
    listEndpoint: '/compliance-acknowledgements',
    detailEndpoint: (id) => `/compliance-acknowledgements/${id}`,
    description: 'Assigned policy and document acknowledgements with status tracking.',
    columns: [
      { key: 'document_title', label: 'Document Title' },
      { key: 'document_type', label: 'Type' },
      { key: 'version', label: 'Version' },
      { key: 'status', label: 'Status', render: (item) => renderBadge(item, 'status') },
      { key: 'assigned_at', label: 'Assigned', render: (item) => renderDateTime(item, 'assigned_at') },
    ],
    detailSections: [
      {
        title: 'Acknowledgement Summary',
        fields: [
          { key: 'document_title', label: 'Document Title' },
          { key: 'document_type', label: 'Document Type' },
          { key: 'version', label: 'Version' },
          { key: 'status', label: 'Status', badge: true },
          { key: 'site_id', label: 'Site', type: 'number' },
          { key: 'assigned_to_user_id', label: 'Assigned To', type: 'number' },
          { key: 'assigned_by_user_id', label: 'Assigned By', type: 'number' },
          { key: 'assigned_at', label: 'Assigned At', type: 'datetime' },
          { key: 'acknowledged_at', label: 'Acknowledged At', type: 'datetime' },
          { key: 'notes', label: 'Notes', type: 'longtext', fullWidth: true },
        ],
      },
    ],
  },
  {
    key: 'permits',
    label: 'Permits',
    singular: 'Permit',
    route: '/permits',
    workflowForm: true,
    icon: Flame,
    attachmentEntityType: 'permit',
    approvalConfig: {
      entityType: 'permit',
      actionType: 'permit_approval',
      requestLabel: 'Request permit approval',
      requestTitle: 'Request Permit Approval',
    },
    listEndpoint: '/permits',
    detailEndpoint: (id) => `/permits/${id}`,
    description: 'Permit-to-work records with lifecycle, risk controls, and attached evidence.',
    columns: [
      { key: 'permit_number', label: 'Permit Number' },
      { key: 'title', label: 'Title' },
      { key: 'permit_type', label: 'Type' },
      { key: 'status', label: 'Status', render: (item) => renderBadge(item, 'status') },
      { key: 'end_datetime', label: 'Ends', render: (item) => renderDateTime(item, 'end_datetime') },
    ],
    detailSections: [
      {
        title: 'Permit Details',
        fields: [
          { key: 'permit_number', label: 'Permit Number' },
          { key: 'permit_type', label: 'Permit Type' },
          { key: 'status', label: 'Status', badge: true },
          { key: 'site_id', label: 'Site', type: 'number' },
          { key: 'area_location', label: 'Area / Location' },
          { key: 'requested_by_user_id', label: 'Requested By', type: 'number' },
          { key: 'issued_by_user_id', label: 'Issued By', type: 'number' },
          { key: 'approved_by_user_id', label: 'Approved By', type: 'number' },
          { key: 'assigned_team_or_contractor', label: 'Team / Contractor' },
          { key: 'start_datetime', label: 'Start', type: 'datetime' },
          { key: 'end_datetime', label: 'End', type: 'datetime' },
          { key: 'approved_at', label: 'Approved At', type: 'datetime' },
          { key: 'closed_at', label: 'Closed At', type: 'datetime' },
        ],
      },
      {
        title: 'Controls & Evidence',
        fields: [
          { key: 'description', label: 'Description', type: 'longtext', fullWidth: true },
          { key: 'risk_summary', label: 'Risk Summary', type: 'longtext', fullWidth: true },
          { key: 'precautions_required', label: 'Precautions Required', type: 'list', fullWidth: true },
          { key: 'ppe_required', label: 'PPE Required', type: 'list', fullWidth: true },
          { key: 'emergency_controls', label: 'Emergency Controls', type: 'list', fullWidth: true },
          { key: 'gas_test_required', label: 'Gas Test Required', type: 'boolean' },
          { key: 'gas_test_results', label: 'Gas Test Results', type: 'object-list', fullWidth: true },
          { key: 'isolation_required', label: 'Isolation Required', type: 'boolean' },
          { key: 'closure_notes', label: 'Closure Notes', type: 'longtext', fullWidth: true },
          { key: 'attachments_metadata', label: 'Attachments', type: 'attachments', fullWidth: true },
        ],
      },
    ],
  },
]

const resourceExportConfig = {
  incidents: {
    csvExportEndpoint: '/exports/incidents.csv',
    reportEndpoint: (id) => `/exports/incidents/${id}/report`,
  },
  hazards: {
    csvExportEndpoint: '/exports/hazards.csv',
    reportEndpoint: (id) => `/exports/hazards/${id}/report`,
  },
  inspections: {
    csvExportEndpoint: '/exports/inspections.csv',
    reportEndpoint: (id) => `/exports/inspections/${id}/report`,
  },
  'corrective-actions': {
    csvExportEndpoint: '/exports/corrective-actions.csv',
    reportEndpoint: (id) => `/exports/corrective-actions/${id}/report`,
  },
  'incident-investigations': {
    csvExportEndpoint: '/exports/incident-investigations.csv',
    reportEndpoint: (id) => `/exports/incident-investigations/${id}/report`,
  },
  'legal-compliance': {
    csvExportEndpoint: '/exports/legal-compliance.csv',
    reportEndpoint: (id) => `/exports/legal-compliance/${id}/report`,
  },
  jsas: {
    csvExportEndpoint: '/exports/jsas.csv',
    reportEndpoint: (id) => `/exports/jsas/${id}/report`,
  },
  contractors: {
    csvExportEndpoint: '/exports/contractors.csv',
    reportEndpoint: (id) => `/exports/contractors/${id}/report`,
  },
  'asset-register': {
    csvExportEndpoint: '/exports/asset-register.csv',
    reportEndpoint: (id) => `/exports/asset-register/${id}/report`,
  },
  'medical-surveillance': {
    csvExportEndpoint: '/exports/medical-surveillance.csv',
    reportEndpoint: (id) => `/exports/medical-surveillance/${id}/report`,
  },
  'emergency-drills': {
    csvExportEndpoint: '/exports/emergency-drills.csv',
    reportEndpoint: (id) => `/exports/emergency-drills/${id}/report`,
  },
  documents: {
    csvExportEndpoint: '/exports/documents.csv',
    reportEndpoint: (id) => `/exports/documents/${id}/report`,
  },
  audits: {
    csvExportEndpoint: '/exports/audits.csv',
    reportEndpoint: (id) => `/exports/audits/${id}/report`,
  },
}

for (const resource of resources) {
  Object.assign(resource, resourceExportConfig[resource.key] ?? {})
}

export const dashboardHighlights = [
  {
    key: 'total_incidents',
    label: 'Total Incidents',
    accent: 'text-rose-700',
    accentBg: 'bg-rose-200',
    description: 'All logged incident records',
  },
  {
    key: 'total_hazards',
    label: 'Total Hazards',
    accent: 'text-amber-700',
    accentBg: 'bg-amber-200',
    description: 'Risk register entries currently tracked',
  },
  {
    key: 'total_inspections',
    label: 'Total Inspections',
    accent: 'text-sky-700',
    accentBg: 'bg-sky-200',
    description: 'Inspection records across all sites',
  },
  {
    key: 'total_corrective_actions',
    label: 'Corrective Actions',
    accent: 'text-emerald-700',
    accentBg: 'bg-emerald-200',
    description: 'Actions requiring assignment and follow-through',
  },
]

export const dashboardBreakdowns = [
  { key: 'incidents_by_status', label: 'Incidents by Status' },
  { key: 'incidents_by_severity', label: 'Incidents by Severity' },
  { key: 'hazards_by_status', label: 'Hazards by Status' },
  { key: 'hazards_by_risk_level', label: 'Hazards by Risk Level' },
  { key: 'inspections_by_status', label: 'Inspections by Status' },
  { key: 'inspections_by_overall_result', label: 'Inspections by Result' },
  { key: 'corrective_actions_by_status', label: 'Actions by Status' },
  { key: 'corrective_actions_by_priority', label: 'Actions by Priority' },
]

export function mapResourceSubtitle(resource, item) {
  if (!item) {
    return ''
  }

  if (resource.key === 'sites') {
    return item.code
  }

  if (resource.key === 'users') {
    return item.email
  }

  if (resource.key === 'roles') {
    return item.description
  }

  if (resource.key === 'audit-logs') {
    return summarizeList([item.resource_type, item.action].filter(Boolean), 2)
  }

  if (resource.key === 'notifications') {
    return `${item.notification_type} • ${item.severity}`
  }

  if (resource.key === 'permits') {
    return item.permit_number
  }

  if (resource.key === 'compliance-acknowledgements') {
    return `${item.document_type} • v${item.version}`
  }

  if (resource.key === 'safety-kpis') {
    return `${formatDate(item.period_start)} to ${formatDate(item.period_end)}`
  }

  if (resource.key === 'incident-investigations') {
    return `Incident #${item.incident_id} • ${item.status}`
  }

  if (resource.key === 'legal-compliance') {
    return summarizeList([item.regulatory_body, item.compliance_status].filter(Boolean), 2)
  }

  if (resource.key === 'jsas') {
    return summarizeList([item.department_or_area, item.status].filter(Boolean), 2)
  }

  if (resource.key === 'contractors') {
    return summarizeList([item.contact_person, item.onboarding_status].filter(Boolean), 2)
  }

  if (resource.key === 'asset-register') {
    return summarizeList([item.asset_tag, item.condition_status].filter(Boolean), 2)
  }

  if (resource.key === 'medical-surveillance') {
    return summarizeList([item.surveillance_type, item.status].filter(Boolean), 2)
  }

  if (resource.key === 'emergency-drills') {
    return summarizeList([item.emergency_type, item.status].filter(Boolean), 2)
  }

  if (resource.key === 'documents') {
    return summarizeList([item.document_type, `v${item.version}`].filter(Boolean), 2)
  }

  if (resource.key === 'audits') {
    return summarizeList([item.audit_type, item.status].filter(Boolean), 2)
  }

  if (resource.key === 'notification-deliveries') {
    return summarizeList([item.channel, item.status].filter(Boolean), 2)
  }

  if (resource.key === 'job-runs') {
    return summarizeList([item.job_name, item.status].filter(Boolean), 2)
  }

  return summarizeList(
    [item.status, item.severity, item.priority, item.risk_level].filter(Boolean),
    2,
  )
}
