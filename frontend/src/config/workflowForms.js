import { canUseUserReferences } from '../lib/rbac.js'

function toLocalDateTimeInput(value) {
  if (!value) {
    return ''
  }

  const date = new Date(value)
  const offset = date.getTimezoneOffset()
  const localDate = new Date(date.getTime() - offset * 60000)
  return localDate.toISOString().slice(0, 16)
}

function toIsoDateTime(value) {
  if (!value) {
    return null
  }

  return new Date(value).toISOString()
}

function parseLineList(value) {
  if (!value) {
    return []
  }

  return value
    .split('\n')
    .map((entry) => entry.trim())
    .filter(Boolean)
}

function formatLineList(values) {
  return Array.isArray(values) ? values.join('\n') : ''
}

function parseIdList(value) {
  if (!value) {
    return []
  }

  return value
    .split(/[\n,]+/)
    .map((entry) => Number(entry.trim()))
    .filter((entry) => Number.isInteger(entry) && entry > 0)
}

function formatIdList(values) {
  return Array.isArray(values) ? values.join(', ') : ''
}

function parseChecklistItems(value) {
  if (!value) {
    return []
  }

  return value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [itemName = '', result = 'compliant', comment = '', linkedHazardId = '', actionRequired = 'no'] =
        line.split('|').map((part) => part.trim())

      return {
        item_name: itemName,
        result: result || 'compliant',
        comment: comment || null,
        linked_hazard_id:
          linkedHazardId && Number.isInteger(Number(linkedHazardId))
            ? Number(linkedHazardId)
            : null,
        action_required: ['yes', 'true', '1'].includes(actionRequired.toLowerCase()),
      }
    })
}

function formatChecklistItems(items) {
  if (!Array.isArray(items) || !items.length) {
    return ''
  }

  return items
    .map((item) =>
      [
        item.item_name ?? '',
        item.result ?? 'compliant',
        item.comment ?? '',
        item.linked_hazard_id ?? '',
        item.action_required ? 'yes' : 'no',
      ].join(' | '),
    )
    .join('\n')
}

function parseGasTestResults(value) {
  if (!value) {
    return []
  }

  return value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [testName = '', result = '', testedBy = ''] = line
        .split('|')
        .map((part) => part.trim())

      return {
        test_name: testName,
        result: result || 'Pending',
        tested_by: testedBy || null,
        tested_at: null,
      }
    })
}

function formatGasTestResults(items) {
  if (!Array.isArray(items) || !items.length) {
    return ''
  }

  return items
    .map((item) => [item.test_name ?? '', item.result ?? '', item.tested_by ?? ''].join(' | '))
    .join('\n')
}

function parseWitnessStatements(value) {
  if (!value) {
    return []
  }

  return value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [name = '', statement = ''] = line.split('|').map((part) => part.trim())
      return {
        name,
        statement,
      }
    })
    .filter((item) => item.name && item.statement)
}

function formatWitnessStatements(items) {
  if (!Array.isArray(items) || !items.length) {
    return ''
  }

  return items
    .map((item) => [item.name ?? '', item.statement ?? ''].join(' | '))
    .join('\n')
}

function parseAttendanceRecords(value) {
  if (!value) {
    return []
  }

  return value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [name = '', attendance = 'present', notes = ''] = line.split('|').map((part) => part.trim())
      return {
        name,
        attendance: attendance || 'present',
        notes: notes || null,
      }
    })
    .filter((item) => item.name)
}

function formatAttendanceRecords(items) {
  if (!Array.isArray(items) || !items.length) {
    return ''
  }

  return items
    .map((item) => [item.name ?? '', item.attendance ?? 'present', item.notes ?? ''].join(' | '))
    .join('\n')
}

function baseTextField(name, label, required = false) {
  return { name, label, type: 'text', required }
}

function buildSelectOptions(values) {
  return values.map((value) => ({ value, label: value.replaceAll('_', ' ') }))
}

function getPrimaryRoleId(item) {
  if (!item) {
    return ''
  }

  if (!Array.isArray(item.roles) || item.roles.length === 0) {
    return ''
  }

  const primaryRole =
    item.roles.find((role) => role.name === item.primary_role) ??
    item.roles.find((role) => Array.isArray(item.role_names) && item.role_names.includes(role.name)) ??
    item.roles[0]

  return primaryRole?.id ? String(primaryRole.id) : ''
}

export const workflowFormConfigs = {
  sites: {
    createTitle: 'Create Site',
    editTitle: 'Edit Site',
    description: 'Keep the site profile lightweight and usable for demos.',
    fields: [
      baseTextField('name', 'Site name', true),
      baseTextField('code', 'Code', true),
      { name: 'address', label: 'Address', type: 'textarea' },
    ],
    getInitialValues: (item) => ({
      name: item?.name ?? '',
      code: item?.code ?? '',
      address: item?.address ?? '',
    }),
    validate(values) {
      const errors = {}
      if (!values.name || values.name.trim().length < 2) {
        errors.name = 'Site name must be at least 2 characters.'
      }
      if (!values.code || values.code.trim().length < 2) {
        errors.code = 'Site code must be at least 2 characters.'
      }
      return errors
    },
    buildPayload: (values) => ({
      name: values.name.trim(),
      code: values.code.trim(),
      address: values.address.trim() || null,
    }),
  },
  users: {
    createTitle: 'Create User',
    editTitle: 'Edit User',
    description: 'Manage admin-owned user accounts, their primary role assignment, and optional site scope.',
    refs: ['sites', 'roles'],
    fields: [
      { name: 'email', label: 'Email', type: 'email', required: true },
      baseTextField('full_name', 'Full name', true),
      baseTextField('phone_number', 'Phone number'),
      {
        name: 'password',
        label: 'Password',
        type: 'password',
        required: true,
        visible: ({ mode }) => mode === 'create',
      },
      {
        name: 'role_id',
        label: 'Primary role',
        type: 'select',
        required: true,
        optionsSource: 'roles',
      },
      {
        name: 'assigned_site_id',
        label: 'Assigned site',
        type: 'select',
        optionsSource: 'sites',
        helperText: 'Leave blank for global-access roles.',
      },
      {
        name: 'is_active',
        label: 'Active account',
        type: 'checkbox',
        checkboxLabel: 'User can sign in and access assigned modules.',
      },
    ],
    getInitialValues: (item) => ({
      email: item?.email ?? '',
      full_name: item?.full_name ?? '',
      phone_number: item?.phone_number ?? '',
      password: '',
      role_id: getPrimaryRoleId(item),
      assigned_site_id: item?.assigned_site_id ? String(item.assigned_site_id) : '',
      is_active: item?.is_active ?? true,
    }),
    validate(values, { mode }) {
      const errors = {}
      if (!values.email || !String(values.email).trim()) {
        errors.email = 'Email is required.'
      }
      if (!values.full_name || values.full_name.trim().length < 2) {
        errors.full_name = 'Full name must be at least 2 characters.'
      }
      if (mode === 'create' && (!values.password || values.password.length < 8)) {
        errors.password = 'Password must be at least 8 characters.'
      }
      if (!values.role_id) {
        errors.role_id = 'Select a role.'
      }
      return errors
    },
    buildPayload: (values, { mode }) => {
      const payload = {
        email: values.email.trim(),
        full_name: values.full_name.trim(),
        phone_number: values.phone_number.trim() || null,
        is_active: Boolean(values.is_active),
        assigned_site_id: values.assigned_site_id ? Number(values.assigned_site_id) : null,
        role_ids: values.role_id ? [Number(values.role_id)] : [],
      }

      if (mode === 'create') {
        return {
          ...payload,
          password: values.password,
        }
      }

      return {
        ...payload,
        ...(values.password ? { password: values.password } : {}),
      }
    },
  },
  roles: {
    createTitle: 'Create Role',
    editTitle: 'Edit Role',
    description: 'Define the role name and short description exposed across the admin console.',
    fields: [
      baseTextField('name', 'Role name', true),
      { name: 'description', label: 'Description', type: 'textarea' },
    ],
    getInitialValues: (item) => ({
      name: item?.name ?? '',
      description: item?.description ?? '',
    }),
    validate(values) {
      const errors = {}
      if (!values.name || values.name.trim().length < 2) {
        errors.name = 'Role name must be at least 2 characters.'
      }
      return errors
    },
    buildPayload: (values) => ({
      name: values.name.trim(),
      description: values.description.trim() || null,
    }),
  },
  incidents: {
    createTitle: 'Create Incident',
    editTitle: 'Edit Incident',
    description: 'Capture the key incident facts with as little ceremony as possible.',
    refs: ['sites'],
    fields: [
      { name: 'site_id', label: 'Site', type: 'select', required: true, optionsSource: 'sites' },
      baseTextField('title', 'Title', true),
      { name: 'description', label: 'Description', type: 'textarea', required: true },
      {
        name: 'severity',
        label: 'Severity',
        type: 'select',
        required: true,
        options: buildSelectOptions(['low', 'medium', 'high', 'critical']),
      },
      {
        name: 'status',
        label: 'Status',
        type: 'select',
        required: true,
        options: buildSelectOptions(['open', 'investigating', 'resolved', 'closed']),
      },
      { name: 'is_recordable', label: 'Recordable case', type: 'checkbox' },
      { name: 'is_lost_time', label: 'Lost time case', type: 'checkbox' },
      { name: 'occurred_at', label: 'Occurred at', type: 'datetime-local', required: true },
    ],
    getInitialValues: (item) => ({
      site_id: item?.site_id ? String(item.site_id) : '',
      title: item?.title ?? '',
      description: item?.description ?? '',
      severity: item?.severity ?? 'medium',
      status: item?.status ?? 'open',
      is_recordable: Boolean(item?.is_recordable),
      is_lost_time: Boolean(item?.is_lost_time),
      occurred_at: toLocalDateTimeInput(item?.occurred_at) || toLocalDateTimeInput(new Date().toISOString()),
    }),
    validate(values) {
      const errors = {}
      if (!values.site_id) errors.site_id = 'Select a site.'
      if (!values.title || values.title.trim().length < 2) errors.title = 'Title is required.'
      if (!values.description || values.description.trim().length < 2) errors.description = 'Description is required.'
      if (!values.occurred_at) errors.occurred_at = 'Occurrence time is required.'
      return errors
    },
    buildPayload: (values) => ({
      site_id: Number(values.site_id),
      title: values.title.trim(),
      description: values.description.trim(),
      severity: values.severity,
      status: values.status,
      is_recordable: Boolean(values.is_recordable || values.is_lost_time),
      is_lost_time: Boolean(values.is_lost_time),
      occurred_at: toIsoDateTime(values.occurred_at),
      attachments_metadata: [],
    }),
  },
  'safety-kpis': {
    createTitle: 'Create Safety KPI Record',
    editTitle: 'Edit Safety KPI Record',
    description: 'Capture hours worked for a reporting period and let the system calculate TRIFR and LTIFR.',
    refs: ['sites'],
    fields: [
      { name: 'site_id', label: 'Site', type: 'select', required: true, optionsSource: 'sites' },
      baseTextField('reporting_label', 'Reporting label'),
      { name: 'period_start', label: 'Period start', type: 'date', required: true },
      { name: 'period_end', label: 'Period end', type: 'date', required: true },
      { name: 'hours_worked', label: 'Hours worked', type: 'number', required: true, min: 0 },
      { name: 'employees_count', label: 'Employees', type: 'number', min: 0 },
      { name: 'contractors_count', label: 'Contractors', type: 'number', min: 0 },
      { name: 'notes', label: 'Notes', type: 'textarea' },
    ],
    getInitialValues: (item) => ({
      site_id: item?.site_id ? String(item.site_id) : '',
      reporting_label: item?.reporting_label ?? '',
      period_start: item?.period_start ?? '',
      period_end: item?.period_end ?? '',
      hours_worked: item?.hours_worked ? String(item.hours_worked) : '',
      employees_count: item?.employees_count ? String(item.employees_count) : '',
      contractors_count: item?.contractors_count ? String(item.contractors_count) : '',
      notes: item?.notes ?? '',
    }),
    validate(values) {
      const errors = {}
      if (!values.site_id) errors.site_id = 'Select a site.'
      if (!values.period_start) errors.period_start = 'Period start is required.'
      if (!values.period_end) errors.period_end = 'Period end is required.'
      if (!values.hours_worked && values.hours_worked !== 0 && values.hours_worked !== '0') {
        errors.hours_worked = 'Hours worked are required.'
      }
      const hoursWorked = Number(values.hours_worked)
      if (Number.isNaN(hoursWorked) || hoursWorked < 0) {
        errors.hours_worked = 'Hours worked must be zero or greater.'
      }
      if (
        values.period_start &&
        values.period_end &&
        new Date(values.period_start) > new Date(values.period_end)
      ) {
        errors.period_end = 'Period end must be on or after the period start.'
      }
      return errors
    },
    buildPayload: (values) => ({
      site_id: Number(values.site_id),
      reporting_label: values.reporting_label.trim() || null,
      period_start: values.period_start,
      period_end: values.period_end,
      hours_worked: Number(values.hours_worked),
      employees_count: values.employees_count ? Number(values.employees_count) : null,
      contractors_count: values.contractors_count ? Number(values.contractors_count) : null,
      notes: values.notes.trim() || null,
    }),
  },
  'incident-investigations': {
    createTitle: 'Create Incident Investigation',
    editTitle: 'Edit Incident Investigation',
    description: 'Capture investigation ownership, witness input, cause analysis, and recommendations linked to an incident.',
    refs: ['users'],
    fields: [
      { name: 'incident_id', label: 'Incident ID', type: 'number', required: true },
      {
        name: 'investigation_lead_user_id',
        label: 'Investigation lead',
        type: 'select',
        optionsSource: 'users',
        visible: ({ user }) => canUseUserReferences(user),
      },
      { name: 'status', label: 'Status', type: 'select', required: true, options: buildSelectOptions(['draft', 'in_progress', 'pending_approval', 'approved', 'closed']) },
      { name: 'target_completion_date', label: 'Target completion date', type: 'date' },
      {
        name: 'approved_by_user_id',
        label: 'Approver',
        type: 'select',
        optionsSource: 'users',
        visible: ({ user }) => canUseUserReferences(user),
      },
      { name: 'investigation_team', label: 'Investigation team', type: 'textarea', helperText: 'One team member per line.' },
      { name: 'witness_statements_text', label: 'Witness statements', type: 'textarea', helperText: 'One line per statement: name | statement.' },
      { name: 'immediate_causes', label: 'Immediate causes', type: 'textarea', helperText: 'One cause per line.' },
      { name: 'underlying_causes', label: 'Underlying causes', type: 'textarea', helperText: 'One cause per line.' },
      { name: 'root_cause', label: 'Root cause', type: 'textarea' },
      { name: 'five_whys', label: 'Five whys', type: 'textarea', helperText: 'One why per line.' },
      { name: 'contributing_factors', label: 'Contributing factors', type: 'textarea', helperText: 'One factor per line.' },
      { name: 'recommendations', label: 'Recommendations', type: 'textarea', helperText: 'One recommendation per line.' },
    ],
    getInitialValues: (item) => ({
      incident_id: item?.incident_id ? String(item.incident_id) : '',
      investigation_lead_user_id: item?.investigation_lead_user_id ? String(item.investigation_lead_user_id) : '',
      status: item?.status ?? 'draft',
      target_completion_date: item?.target_completion_date ?? '',
      approved_by_user_id: item?.approved_by_user_id ? String(item.approved_by_user_id) : '',
      investigation_team: formatLineList(item?.investigation_team),
      witness_statements_text: formatWitnessStatements(item?.witness_statements),
      immediate_causes: formatLineList(item?.immediate_causes),
      underlying_causes: formatLineList(item?.underlying_causes),
      root_cause: item?.root_cause ?? '',
      five_whys: formatLineList(item?.five_whys),
      contributing_factors: formatLineList(item?.contributing_factors),
      recommendations: formatLineList(item?.recommendations),
    }),
    validate(values) {
      const errors = {}
      if (!values.incident_id) errors.incident_id = 'Incident ID is required.'
      if (!values.status) errors.status = 'Status is required.'
      return errors
    },
    buildPayload: (values) => ({
      incident_id: Number(values.incident_id),
      investigation_lead_user_id: values.investigation_lead_user_id ? Number(values.investigation_lead_user_id) : null,
      investigation_team: parseLineList(values.investigation_team),
      witness_statements: parseWitnessStatements(values.witness_statements_text),
      immediate_causes: parseLineList(values.immediate_causes),
      underlying_causes: parseLineList(values.underlying_causes),
      root_cause: values.root_cause.trim() || null,
      five_whys: parseLineList(values.five_whys),
      contributing_factors: parseLineList(values.contributing_factors),
      recommendations: parseLineList(values.recommendations),
      status: values.status,
      target_completion_date: values.target_completion_date || null,
      approved_by_user_id: values.approved_by_user_id ? Number(values.approved_by_user_id) : null,
      attachments_metadata: [],
    }),
  },
  'legal-compliance': {
    createTitle: 'Create Legal Compliance Item',
    editTitle: 'Edit Legal Compliance Item',
    description: 'Maintain the legal compliance register with ownership, review frequency, and evidence expectations.',
    refs: ['sites', 'users'],
    fields: [
      baseTextField('title', 'Title', true),
      baseTextField('regulatory_body', 'Regulatory body', true),
      baseTextField('legal_reference', 'Legal reference', true),
      { name: 'requirement_summary', label: 'Requirement summary', type: 'textarea', required: true },
      { name: 'site_id', label: 'Site', type: 'select', optionsSource: 'sites' },
      {
        name: 'owner_user_id',
        label: 'Owner',
        type: 'select',
        required: true,
        optionsSource: 'users',
        visible: ({ user }) => canUseUserReferences(user),
      },
      { name: 'compliance_status', label: 'Compliance status', type: 'select', required: true, options: buildSelectOptions(['compliant', 'partial', 'non_compliant', 'not_applicable', 'pending_review']) },
      baseTextField('review_frequency', 'Review frequency', true),
      { name: 'next_review_date', label: 'Next review date', type: 'date' },
      { name: 'evidence_required', label: 'Evidence required', type: 'checkbox' },
      { name: 'notes', label: 'Notes', type: 'textarea' },
    ],
    getInitialValues: (item, currentUser) => ({
      title: item?.title ?? '',
      regulatory_body: item?.regulatory_body ?? '',
      legal_reference: item?.legal_reference ?? '',
      requirement_summary: item?.requirement_summary ?? '',
      site_id: item?.site_id ? String(item.site_id) : '',
      owner_user_id: item?.owner_user_id ? String(item.owner_user_id) : String(currentUser?.id ?? ''),
      compliance_status: item?.compliance_status ?? 'pending_review',
      review_frequency: item?.review_frequency ?? '',
      next_review_date: item?.next_review_date ?? '',
      evidence_required: Boolean(item?.evidence_required),
      notes: item?.notes ?? '',
    }),
    validate(values, { user }) {
      const errors = {}
      if (!values.title || values.title.trim().length < 2) errors.title = 'Title is required.'
      if (!values.regulatory_body || values.regulatory_body.trim().length < 2) errors.regulatory_body = 'Regulatory body is required.'
      if (!values.legal_reference || values.legal_reference.trim().length < 2) errors.legal_reference = 'Legal reference is required.'
      if (!values.requirement_summary || values.requirement_summary.trim().length < 2) errors.requirement_summary = 'Requirement summary is required.'
      if (canUseUserReferences(user) && !values.owner_user_id) errors.owner_user_id = 'Select an owner.'
      if (!values.review_frequency || values.review_frequency.trim().length < 2) errors.review_frequency = 'Review frequency is required.'
      return errors
    },
    buildPayload: (values, { user }) => ({
      title: values.title.trim(),
      regulatory_body: values.regulatory_body.trim(),
      legal_reference: values.legal_reference.trim(),
      requirement_summary: values.requirement_summary.trim(),
      site_id: values.site_id ? Number(values.site_id) : null,
      owner_user_id: canUseUserReferences(user) ? Number(values.owner_user_id) : Number(user?.id),
      compliance_status: values.compliance_status,
      review_frequency: values.review_frequency.trim(),
      next_review_date: values.next_review_date || null,
      evidence_required: Boolean(values.evidence_required),
      notes: values.notes.trim() || null,
      attachments_metadata: [],
    }),
  },
  jsas: {
    createTitle: 'Create JSA / Risk Assessment',
    editTitle: 'Edit JSA / Risk Assessment',
    description: 'Document the work steps, hazards, controls, and residual risk before approval and use.',
    refs: ['sites', 'users'],
    fields: [
      baseTextField('title', 'Title', true),
      { name: 'site_id', label: 'Site', type: 'select', required: true, optionsSource: 'sites' },
      baseTextField('department_or_area', 'Department / area', true),
      { name: 'status', label: 'Status', type: 'select', required: true, options: buildSelectOptions(['draft', 'pending_approval', 'approved', 'expired', 'archived']) },
      { name: 'residual_risk_level', label: 'Residual risk level', type: 'select', required: true, options: buildSelectOptions(['low', 'medium', 'high', 'critical']) },
      { name: 'review_date', label: 'Review date', type: 'date' },
      {
        name: 'approved_by_user_id',
        label: 'Approver',
        type: 'select',
        optionsSource: 'users',
        visible: ({ user }) => canUseUserReferences(user),
      },
      { name: 'job_steps', label: 'Job steps', type: 'textarea', helperText: 'One step per line.' },
      { name: 'hazards', label: 'Hazards', type: 'textarea', helperText: 'One hazard per line.' },
      { name: 'controls', label: 'Controls', type: 'textarea', helperText: 'One control per line.' },
      { name: 'ppe_required', label: 'PPE required', type: 'textarea', helperText: 'One PPE item per line.' },
    ],
    getInitialValues: (item) => ({
      title: item?.title ?? '',
      site_id: item?.site_id ? String(item.site_id) : '',
      department_or_area: item?.department_or_area ?? '',
      status: item?.status ?? 'draft',
      residual_risk_level: item?.residual_risk_level ?? 'medium',
      review_date: item?.review_date ?? '',
      approved_by_user_id: item?.approved_by_user_id ? String(item.approved_by_user_id) : '',
      job_steps: formatLineList(item?.job_steps),
      hazards: formatLineList(item?.hazards),
      controls: formatLineList(item?.controls),
      ppe_required: formatLineList(item?.ppe_required),
    }),
    validate(values) {
      const errors = {}
      if (!values.title || values.title.trim().length < 2) errors.title = 'Title is required.'
      if (!values.site_id) errors.site_id = 'Select a site.'
      if (!values.department_or_area || values.department_or_area.trim().length < 2) {
        errors.department_or_area = 'Department or area is required.'
      }
      return errors
    },
    buildPayload: (values) => ({
      title: values.title.trim(),
      site_id: Number(values.site_id),
      department_or_area: values.department_or_area.trim(),
      job_steps: parseLineList(values.job_steps),
      hazards: parseLineList(values.hazards),
      controls: parseLineList(values.controls),
      ppe_required: parseLineList(values.ppe_required),
      residual_risk_level: values.residual_risk_level,
      approved_by_user_id: values.approved_by_user_id ? Number(values.approved_by_user_id) : null,
      status: values.status,
      review_date: values.review_date || null,
      attachments_metadata: [],
    }),
  },
  contractors: {
    createTitle: 'Create Contractor',
    editTitle: 'Edit Contractor',
    description: 'Track contractor onboarding readiness, induction, insurance expiry, and compliance documentation.',
    refs: ['sites'],
    fields: [
      baseTextField('contractor_name', 'Contractor name', true),
      baseTextField('contact_person', 'Contact person', true),
      { name: 'contact_email', label: 'Contact email', type: 'email', required: true },
      baseTextField('contact_phone', 'Contact phone', true),
      { name: 'site_id', label: 'Site', type: 'select', required: true, optionsSource: 'sites' },
      { name: 'work_scope', label: 'Work scope', type: 'textarea', required: true },
      { name: 'onboarding_status', label: 'Onboarding status', type: 'select', required: true, options: buildSelectOptions(['pending', 'in_progress', 'completed']) },
      { name: 'induction_status', label: 'Induction status', type: 'select', required: true, options: buildSelectOptions(['pending', 'completed', 'expired']) },
      { name: 'insurance_expiry_date', label: 'Insurance expiry date', type: 'date' },
      { name: 'compliance_documents_status', label: 'Compliance documents status', type: 'select', required: true, options: buildSelectOptions(['incomplete', 'complete', 'expired']) },
      { name: 'documents_expiry_date', label: 'Documents expiry date', type: 'date' },
      { name: 'approved_for_work', label: 'Approved for work', type: 'checkbox' },
      { name: 'notes', label: 'Notes', type: 'textarea' },
    ],
    getInitialValues: (item) => ({
      contractor_name: item?.contractor_name ?? '',
      contact_person: item?.contact_person ?? '',
      contact_email: item?.contact_email ?? '',
      contact_phone: item?.contact_phone ?? '',
      site_id: item?.site_id ? String(item.site_id) : '',
      work_scope: item?.work_scope ?? '',
      onboarding_status: item?.onboarding_status ?? 'pending',
      induction_status: item?.induction_status ?? 'pending',
      insurance_expiry_date: item?.insurance_expiry_date ?? '',
      compliance_documents_status: item?.compliance_documents_status ?? 'incomplete',
      documents_expiry_date: item?.documents_expiry_date ?? '',
      approved_for_work: Boolean(item?.approved_for_work),
      notes: item?.notes ?? '',
    }),
    validate(values) {
      const errors = {}
      if (!values.contractor_name || values.contractor_name.trim().length < 2) errors.contractor_name = 'Contractor name is required.'
      if (!values.contact_person || values.contact_person.trim().length < 2) errors.contact_person = 'Contact person is required.'
      if (!values.contact_email || !String(values.contact_email).trim()) errors.contact_email = 'Contact email is required.'
      if (!values.contact_phone || values.contact_phone.trim().length < 2) errors.contact_phone = 'Contact phone is required.'
      if (!values.site_id) errors.site_id = 'Select a site.'
      if (!values.work_scope || values.work_scope.trim().length < 2) errors.work_scope = 'Work scope is required.'
      return errors
    },
    buildPayload: (values) => ({
      contractor_name: values.contractor_name.trim(),
      contact_person: values.contact_person.trim(),
      contact_email: values.contact_email.trim(),
      contact_phone: values.contact_phone.trim(),
      site_id: Number(values.site_id),
      work_scope: values.work_scope.trim(),
      onboarding_status: values.onboarding_status,
      induction_status: values.induction_status,
      insurance_expiry_date: values.insurance_expiry_date || null,
      compliance_documents_status: values.compliance_documents_status,
      approved_for_work: Boolean(values.approved_for_work),
      notes: values.notes.trim() || null,
      documents_expiry_date: values.documents_expiry_date || null,
      attachments_metadata: [],
    }),
  },
  'asset-register': {
    createTitle: 'Create Asset Register Item',
    editTitle: 'Edit Asset Register Item',
    description: 'Register equipment, PPE, and emergency assets with inspection dates, assignment, and condition status.',
    refs: ['sites', 'users'],
    fields: [
      { name: 'asset_type', label: 'Asset type', type: 'select', required: true, options: buildSelectOptions(['equipment', 'ppe', 'emergency_equipment', 'fire_extinguisher', 'first_aid_kit']) },
      baseTextField('asset_name', 'Asset name', true),
      baseTextField('asset_tag', 'Asset tag', true),
      { name: 'site_id', label: 'Site', type: 'select', required: true, optionsSource: 'sites' },
      baseTextField('location', 'Location', true),
      {
        name: 'assigned_to_user_id',
        label: 'Assigned to',
        type: 'select',
        optionsSource: 'users',
        visible: ({ user }) => canUseUserReferences(user),
      },
      baseTextField('inspection_frequency', 'Inspection frequency', true),
      { name: 'next_inspection_date', label: 'Next inspection date', type: 'date' },
      { name: 'condition_status', label: 'Condition status', type: 'select', required: true, options: buildSelectOptions(['good', 'needs_attention', 'defective', 'retired']) },
      { name: 'last_inspected_at', label: 'Last inspected at', type: 'datetime-local' },
      { name: 'notes', label: 'Notes', type: 'textarea' },
    ],
    getInitialValues: (item) => ({
      asset_type: item?.asset_type ?? 'equipment',
      asset_name: item?.asset_name ?? '',
      asset_tag: item?.asset_tag ?? '',
      site_id: item?.site_id ? String(item.site_id) : '',
      location: item?.location ?? '',
      assigned_to_user_id: item?.assigned_to_user_id ? String(item.assigned_to_user_id) : '',
      inspection_frequency: item?.inspection_frequency ?? '',
      next_inspection_date: item?.next_inspection_date ?? '',
      condition_status: item?.condition_status ?? 'good',
      last_inspected_at: toLocalDateTimeInput(item?.last_inspected_at),
      notes: item?.notes ?? '',
    }),
    validate(values) {
      const errors = {}
      if (!values.asset_name || values.asset_name.trim().length < 2) errors.asset_name = 'Asset name is required.'
      if (!values.asset_tag || values.asset_tag.trim().length < 2) errors.asset_tag = 'Asset tag is required.'
      if (!values.site_id) errors.site_id = 'Select a site.'
      if (!values.location || values.location.trim().length < 2) errors.location = 'Location is required.'
      if (!values.inspection_frequency || values.inspection_frequency.trim().length < 2) {
        errors.inspection_frequency = 'Inspection frequency is required.'
      }
      return errors
    },
    buildPayload: (values) => ({
      asset_type: values.asset_type,
      asset_name: values.asset_name.trim(),
      asset_tag: values.asset_tag.trim(),
      site_id: Number(values.site_id),
      location: values.location.trim(),
      assigned_to_user_id: values.assigned_to_user_id ? Number(values.assigned_to_user_id) : null,
      inspection_frequency: values.inspection_frequency.trim(),
      next_inspection_date: values.next_inspection_date || null,
      condition_status: values.condition_status,
      last_inspected_at: values.last_inspected_at ? toIsoDateTime(values.last_inspected_at) : null,
      notes: values.notes.trim() || null,
      attachments_metadata: [],
    }),
  },
  'safety-communications': {
    createTitle: 'Create Safety Communication',
    editTitle: 'Edit Safety Communication',
    description: 'Publish toolbox talks, safety alerts, posters, signage, and campaigns to the right site.',
    refs: ['sites', 'users'],
    fields: [
      { name: 'site_id', label: 'Site', type: 'select', required: true, optionsSource: 'sites' },
      baseTextField('title', 'Title', true),
      {
        name: 'communication_type',
        label: 'Type',
        type: 'select',
        required: true,
        options: buildSelectOptions(['toolbox_talk', 'safety_alert', 'poster', 'signage', 'campaign']),
      },
      {
        name: 'status',
        label: 'Status',
        type: 'select',
        required: true,
        options: buildSelectOptions(['draft', 'published', 'archived']),
      },
      { name: 'summary', label: 'Summary', type: 'textarea', required: true },
      { name: 'details', label: 'Details', type: 'textarea' },
      baseTextField('audience', 'Audience'),
      {
        name: 'owner_user_id',
        label: 'Owner',
        type: 'select',
        optionsSource: 'users',
        visible: ({ user }) => canUseUserReferences(user),
      },
      { name: 'requires_acknowledgement', label: 'Requires acknowledgement', type: 'checkbox' },
      { name: 'issued_at', label: 'Issued at', type: 'datetime-local', required: true },
      { name: 'expires_at', label: 'Expires at', type: 'datetime-local' },
    ],
    getInitialValues: (item, currentUser) => ({
      site_id: item?.site_id ? String(item.site_id) : '',
      title: item?.title ?? '',
      communication_type: item?.communication_type ?? 'toolbox_talk',
      status: item?.status ?? 'draft',
      summary: item?.summary ?? '',
      details: item?.details ?? '',
      audience: item?.audience ?? '',
      owner_user_id: item?.owner_user_id ? String(item.owner_user_id) : String(currentUser?.id ?? ''),
      requires_acknowledgement: Boolean(item?.requires_acknowledgement),
      issued_at: toLocalDateTimeInput(item?.issued_at) || toLocalDateTimeInput(new Date().toISOString()),
      expires_at: toLocalDateTimeInput(item?.expires_at),
    }),
    validate(values) {
      const errors = {}
      if (!values.site_id) errors.site_id = 'Select a site.'
      if (!values.title || values.title.trim().length < 2) errors.title = 'Title is required.'
      if (!values.summary || values.summary.trim().length < 2) errors.summary = 'Summary is required.'
      if (!values.issued_at) errors.issued_at = 'Issued date and time are required.'
      if (
        values.issued_at &&
        values.expires_at &&
        new Date(values.issued_at) >= new Date(values.expires_at)
      ) {
        errors.expires_at = 'Expiry must be after the issue date.'
      }
      return errors
    },
    buildPayload: (values) => ({
      site_id: Number(values.site_id),
      title: values.title.trim(),
      communication_type: values.communication_type,
      status: values.status,
      summary: values.summary.trim(),
      details: values.details.trim() || null,
      audience: values.audience.trim() || null,
      owner_user_id: values.owner_user_id ? Number(values.owner_user_id) : null,
      requires_acknowledgement: Boolean(values.requires_acknowledgement),
      issued_at: toIsoDateTime(values.issued_at),
      expires_at: values.expires_at ? toIsoDateTime(values.expires_at) : null,
      attachments_metadata: [],
    }),
  },
  'behaviour-observations': {
    createTitle: 'Create Behaviour Observation',
    editTitle: 'Edit Behaviour Observation',
    description: 'Capture unsafe acts, positive observations, conduct issues, and event safety observations.',
    refs: ['sites'],
    fields: [
      { name: 'site_id', label: 'Site', type: 'select', required: true, optionsSource: 'sites' },
      baseTextField('title', 'Title', true),
      {
        name: 'observation_type',
        label: 'Observation type',
        type: 'select',
        required: true,
        options: buildSelectOptions(['unsafe_act', 'positive_observation', 'conduct_issue', 'event_safety_observation']),
      },
      {
        name: 'status',
        label: 'Status',
        type: 'select',
        required: true,
        options: buildSelectOptions(['open', 'reviewed', 'actioned', 'closed']),
      },
      {
        name: 'severity',
        label: 'Severity',
        type: 'select',
        required: true,
        options: buildSelectOptions(['low', 'medium', 'high']),
      },
      { name: 'description', label: 'Description', type: 'textarea', required: true },
      { name: 'person_involved_name', label: 'Person / team', type: 'text' },
      { name: 'action_required', label: 'Action required', type: 'checkbox' },
      { name: 'immediate_action_taken', label: 'Immediate action taken', type: 'textarea' },
      { name: 'follow_up_notes', label: 'Follow-up notes', type: 'textarea' },
      { name: 'observed_at', label: 'Observed at', type: 'datetime-local', required: true },
    ],
    getInitialValues: (item) => ({
      site_id: item?.site_id ? String(item.site_id) : '',
      title: item?.title ?? '',
      observation_type: item?.observation_type ?? 'unsafe_act',
      status: item?.status ?? 'open',
      severity: item?.severity ?? 'medium',
      description: item?.description ?? '',
      person_involved_name: item?.person_involved_name ?? '',
      action_required: Boolean(item?.action_required),
      immediate_action_taken: item?.immediate_action_taken ?? '',
      follow_up_notes: item?.follow_up_notes ?? '',
      observed_at: toLocalDateTimeInput(item?.observed_at) || toLocalDateTimeInput(new Date().toISOString()),
    }),
    validate(values) {
      const errors = {}
      if (!values.site_id) errors.site_id = 'Select a site.'
      if (!values.title || values.title.trim().length < 2) errors.title = 'Title is required.'
      if (!values.description || values.description.trim().length < 2) errors.description = 'Description is required.'
      if (!values.observed_at) errors.observed_at = 'Observation time is required.'
      return errors
    },
    buildPayload: (values) => ({
      site_id: Number(values.site_id),
      title: values.title.trim(),
      observation_type: values.observation_type,
      status: values.status,
      severity: values.severity,
      description: values.description.trim(),
      person_involved_name: values.person_involved_name.trim() || null,
      action_required: Boolean(values.action_required),
      immediate_action_taken: values.immediate_action_taken.trim() || null,
      follow_up_notes: values.follow_up_notes.trim() || null,
      observed_at: toIsoDateTime(values.observed_at),
      attachments_metadata: [],
    }),
  },
  'medical-surveillance': {
    createTitle: 'Create Medical Surveillance Record',
    editTitle: 'Edit Medical Surveillance Record',
    description: 'Track occupational health surveillance due dates, outcomes, and medical clearance states.',
    refs: ['sites', 'users'],
    fields: [
      {
        name: 'employee_user_id',
        label: 'Employee',
        type: 'select',
        required: true,
        optionsSource: 'users',
        visible: ({ user }) => canUseUserReferences(user),
      },
      { name: 'site_id', label: 'Site', type: 'select', optionsSource: 'sites' },
      baseTextField('surveillance_type', 'Surveillance type', true),
      { name: 'due_date', label: 'Due date', type: 'date', required: true },
      { name: 'completed_at', label: 'Completed at', type: 'datetime-local' },
      { name: 'medical_clearance_status', label: 'Medical clearance', type: 'select', required: true, options: buildSelectOptions(['pending', 'cleared', 'restricted', 'not_cleared']) },
      { name: 'results_summary', label: 'Results summary', type: 'textarea' },
      { name: 'next_due_date', label: 'Next due date', type: 'date' },
      { name: 'notes', label: 'Notes', type: 'textarea' },
    ],
    getInitialValues: (item, currentUser) => ({
      employee_user_id: item?.employee_user_id ? String(item.employee_user_id) : String(currentUser?.id ?? ''),
      site_id: item?.site_id ? String(item.site_id) : '',
      surveillance_type: item?.surveillance_type ?? '',
      due_date: item?.due_date ?? '',
      completed_at: toLocalDateTimeInput(item?.completed_at),
      medical_clearance_status: item?.medical_clearance_status ?? 'pending',
      results_summary: item?.results_summary ?? '',
      next_due_date: item?.next_due_date ?? '',
      notes: item?.notes ?? '',
    }),
    validate(values) {
      const errors = {}
      if (!values.employee_user_id) errors.employee_user_id = 'Select an employee.'
      if (!values.surveillance_type || values.surveillance_type.trim().length < 2) errors.surveillance_type = 'Surveillance type is required.'
      if (!values.due_date) errors.due_date = 'Due date is required.'
      return errors
    },
    buildPayload: (values) => ({
      employee_user_id: Number(values.employee_user_id),
      site_id: values.site_id ? Number(values.site_id) : null,
      surveillance_type: values.surveillance_type.trim(),
      due_date: values.due_date,
      completed_at: toIsoDateTime(values.completed_at),
      medical_clearance_status: values.medical_clearance_status,
      results_summary: values.results_summary.trim() || null,
      next_due_date: values.next_due_date || null,
      notes: values.notes.trim() || null,
      attachments_metadata: [],
    }),
  },
  'emergency-drills': {
    createTitle: 'Create Emergency Drill',
    editTitle: 'Edit Emergency Drill',
    description: 'Schedule drills, capture attendance, and record issues plus corrective actions in a compact format.',
    refs: ['sites'],
    fields: [
      { name: 'site_id', label: 'Site', type: 'select', required: true, optionsSource: 'sites' },
      baseTextField('emergency_type', 'Emergency type', true),
      { name: 'drill_date', label: 'Drill date', type: 'date', required: true },
      { name: 'next_drill_date', label: 'Next drill date', type: 'date' },
      { name: 'participants', label: 'Participants', type: 'textarea', helperText: 'One participant per line.' },
      { name: 'attendance_records_text', label: 'Attendance records', type: 'textarea', helperText: 'One line per attendee: name | present/absent | notes.' },
      { name: 'outcome', label: 'Outcome', type: 'textarea' },
      { name: 'issues_found', label: 'Issues found', type: 'textarea', helperText: 'One issue per line.' },
      { name: 'corrective_actions', label: 'Corrective actions', type: 'textarea', helperText: 'One corrective action per line.' },
      { name: 'status', label: 'Status', type: 'select', required: true, options: buildSelectOptions(['scheduled', 'completed', 'overdue', 'archived']) },
    ],
    getInitialValues: (item) => ({
      site_id: item?.site_id ? String(item.site_id) : '',
      emergency_type: item?.emergency_type ?? 'fire',
      drill_date: item?.drill_date ?? '',
      next_drill_date: item?.next_drill_date ?? '',
      participants: formatLineList(item?.participants),
      attendance_records_text: formatAttendanceRecords(item?.attendance_records),
      outcome: item?.outcome ?? '',
      issues_found: formatLineList(item?.issues_found),
      corrective_actions: formatLineList(item?.corrective_actions),
      status: item?.status ?? 'scheduled',
    }),
    validate(values) {
      const errors = {}
      if (!values.site_id) errors.site_id = 'Select a site.'
      if (!values.emergency_type || values.emergency_type.trim().length < 2) errors.emergency_type = 'Emergency type is required.'
      if (!values.drill_date) errors.drill_date = 'Drill date is required.'
      return errors
    },
    buildPayload: (values) => ({
      site_id: Number(values.site_id),
      emergency_type: values.emergency_type.trim(),
      drill_date: values.drill_date,
      next_drill_date: values.next_drill_date || null,
      participants: parseLineList(values.participants),
      attendance_records: parseAttendanceRecords(values.attendance_records_text),
      outcome: values.outcome.trim() || null,
      issues_found: parseLineList(values.issues_found),
      corrective_actions: parseLineList(values.corrective_actions),
      status: values.status,
      attachments_metadata: [],
    }),
  },
  documents: {
    createTitle: 'Create Controlled Document',
    editTitle: 'Edit Controlled Document',
    description: 'Maintain versioned policies, SOPs, procedures, and forms with acknowledgement assignment and approval workflow.',
    refs: ['sites', 'users'],
    fields: [
      baseTextField('title', 'Title', true),
      { name: 'document_type', label: 'Document type', type: 'select', required: true, options: buildSelectOptions(['policy', 'sop', 'procedure', 'form']) },
      baseTextField('version', 'Version', true),
      { name: 'site_id', label: 'Site', type: 'select', optionsSource: 'sites' },
      { name: 'status', label: 'Status', type: 'select', required: true, options: buildSelectOptions(['draft', 'pending_approval', 'approved', 'expired', 'archived']) },
      {
        name: 'approved_by_user_id',
        label: 'Approved by',
        type: 'select',
        optionsSource: 'users',
        visible: ({ user }) => canUseUserReferences(user),
      },
      { name: 'approved_at', label: 'Approved at', type: 'datetime-local' },
      { name: 'expiry_date', label: 'Expiry date', type: 'date' },
      { name: 'acknowledgement_required', label: 'Acknowledgement required', type: 'checkbox' },
      { name: 'acknowledgement_user_ids_text', label: 'Acknowledgement user IDs', type: 'textarea', helperText: 'Optional comma or newline separated user IDs.' },
      { name: 'supersedes_document_id', label: 'Supersedes document ID', type: 'number' },
    ],
    getInitialValues: (item) => ({
      title: item?.title ?? '',
      document_type: item?.document_type ?? 'policy',
      version: item?.version ?? '1.0',
      site_id: item?.site_id ? String(item.site_id) : '',
      status: item?.status ?? 'draft',
      approved_by_user_id: item?.approved_by_user_id ? String(item.approved_by_user_id) : '',
      approved_at: toLocalDateTimeInput(item?.approved_at),
      expiry_date: item?.expiry_date ?? '',
      acknowledgement_required: Boolean(item?.acknowledgement_required),
      acknowledgement_user_ids_text: formatIdList(item?.acknowledgement_user_ids),
      supersedes_document_id: item?.supersedes_document_id ? String(item.supersedes_document_id) : '',
    }),
    validate(values) {
      const errors = {}
      if (!values.title || values.title.trim().length < 2) errors.title = 'Title is required.'
      if (!values.version || values.version.trim().length < 1) errors.version = 'Version is required.'
      if (values.status === 'approved' && !values.approved_by_user_id) {
        errors.approved_by_user_id = 'Approved documents need an approver.'
      }
      return errors
    },
    buildPayload: (values) => ({
      title: values.title.trim(),
      document_type: values.document_type,
      version: values.version.trim(),
      site_id: values.site_id ? Number(values.site_id) : null,
      status: values.status,
      approved_by_user_id: values.approved_by_user_id ? Number(values.approved_by_user_id) : null,
      approved_at: toIsoDateTime(values.approved_at),
      expiry_date: values.expiry_date || null,
      acknowledgement_required: Boolean(values.acknowledgement_required),
      acknowledgement_user_ids: parseIdList(values.acknowledgement_user_ids_text),
      supersedes_document_id: values.supersedes_document_id ? Number(values.supersedes_document_id) : null,
      attachments_metadata: [],
    }),
  },
  audits: {
    createTitle: 'Create Audit',
    editTitle: 'Edit Audit',
    description: 'Capture audit scope, findings, non-conformances, recommendations, and linked corrective actions.',
    refs: ['sites', 'users'],
    fields: [
      { name: 'audit_type', label: 'Audit type', type: 'select', required: true, options: buildSelectOptions(['internal', 'external', 'compliance']) },
      { name: 'site_id', label: 'Site', type: 'select', required: true, optionsSource: 'sites' },
      {
        name: 'auditor_user_id',
        label: 'Auditor',
        type: 'select',
        required: true,
        optionsSource: 'users',
        visible: ({ user }) => canUseUserReferences(user),
      },
      { name: 'audit_date', label: 'Audit date', type: 'date', required: true },
      { name: 'status', label: 'Status', type: 'select', required: true, options: buildSelectOptions(['open', 'closed']) },
      { name: 'audit_score', label: 'Audit score', type: 'number', min: 0, max: 100 },
      { name: 'findings', label: 'Findings', type: 'textarea', helperText: 'One finding per line.' },
      { name: 'non_conformances', label: 'Non-conformances', type: 'textarea', helperText: 'One non-conformance per line.' },
      { name: 'recommendations', label: 'Recommendations', type: 'textarea', helperText: 'One recommendation per line.' },
      { name: 'corrective_action_ids_text', label: 'Corrective action IDs', type: 'textarea', helperText: 'Optional comma or newline separated IDs.' },
    ],
    getInitialValues: (item, currentUser) => ({
      audit_type: item?.audit_type ?? 'internal',
      site_id: item?.site_id ? String(item.site_id) : '',
      auditor_user_id: item?.auditor_user_id ? String(item.auditor_user_id) : String(currentUser?.id ?? ''),
      audit_date: item?.audit_date ?? '',
      status: item?.status ?? 'open',
      audit_score: item?.audit_score ? String(item.audit_score) : '',
      findings: formatLineList(item?.findings),
      non_conformances: formatLineList(item?.non_conformances),
      recommendations: formatLineList(item?.recommendations),
      corrective_action_ids_text: formatIdList(item?.corrective_action_ids),
    }),
    validate(values) {
      const errors = {}
      if (!values.site_id) errors.site_id = 'Select a site.'
      if (!values.auditor_user_id) errors.auditor_user_id = 'Select an auditor.'
      if (!values.audit_date) errors.audit_date = 'Audit date is required.'
      return errors
    },
    buildPayload: (values) => ({
      audit_type: values.audit_type,
      site_id: Number(values.site_id),
      auditor_user_id: Number(values.auditor_user_id),
      audit_date: values.audit_date,
      status: values.status,
      audit_score: values.audit_score ? Number(values.audit_score) : null,
      findings: parseLineList(values.findings),
      non_conformances: parseLineList(values.non_conformances),
      recommendations: parseLineList(values.recommendations),
      corrective_action_ids: parseIdList(values.corrective_action_ids_text),
      attachments_metadata: [],
    }),
  },
  hazards: {
    createTitle: 'Create Hazard',
    editTitle: 'Edit Hazard',
    description: 'Capture a practical risk register entry with ownership and controls.',
    refs: ['sites', 'users'],
    fields: [
      { name: 'site_id', label: 'Site', type: 'select', required: true, optionsSource: 'sites' },
      baseTextField('title', 'Title', true),
      { name: 'description', label: 'Description', type: 'textarea', required: true },
      { name: 'likelihood', label: 'Likelihood (1-5)', type: 'number', required: true, min: 1, max: 5 },
      { name: 'impact', label: 'Impact (1-5)', type: 'number', required: true, min: 1, max: 5 },
      {
        name: 'status',
        label: 'Status',
        type: 'select',
        required: true,
        options: buildSelectOptions(['open', 'controlled', 'closed']),
      },
      {
        name: 'owner_user_id',
        label: 'Owner',
        type: 'select',
        optionsSource: 'users',
        visible: ({ user }) => canUseUserReferences(user),
      },
      { name: 'due_date', label: 'Due date', type: 'date' },
      { name: 'review_date', label: 'Review date', type: 'date' },
      { name: 'existing_controls', label: 'Existing controls', type: 'textarea', helperText: 'One control per line.' },
      { name: 'additional_controls', label: 'Additional controls', type: 'textarea', helperText: 'One control per line.' },
      { name: 'incident_id', label: 'Linked incident ID', type: 'number' },
    ],
    getInitialValues: (item, currentUser) => ({
      site_id: item?.site_id ? String(item.site_id) : '',
      title: item?.title ?? '',
      description: item?.description ?? '',
      likelihood: item?.likelihood ? String(item.likelihood) : '3',
      impact: item?.impact ? String(item.impact) : '3',
      status: item?.status ?? 'open',
      owner_user_id: item?.owner_user_id ? String(item.owner_user_id) : String(currentUser?.id ?? ''),
      due_date: item?.due_date ?? '',
      review_date: item?.review_date ?? '',
      existing_controls: formatLineList(item?.existing_controls),
      additional_controls: formatLineList(item?.additional_controls),
      incident_id: item?.incident_id ? String(item.incident_id) : '',
    }),
    validate(values) {
      const errors = {}
      if (!values.site_id) errors.site_id = 'Select a site.'
      if (!values.title || values.title.trim().length < 2) errors.title = 'Title is required.'
      if (!values.description || values.description.trim().length < 2) errors.description = 'Description is required.'
      const likelihood = Number(values.likelihood)
      const impact = Number(values.impact)
      if (!Number.isInteger(likelihood) || likelihood < 1 || likelihood > 5) {
        errors.likelihood = 'Likelihood must be between 1 and 5.'
      }
      if (!Number.isInteger(impact) || impact < 1 || impact > 5) {
        errors.impact = 'Impact must be between 1 and 5.'
      }
      return errors
    },
    buildPayload: (values) => ({
      site_id: Number(values.site_id),
      title: values.title.trim(),
      description: values.description.trim(),
      likelihood: Number(values.likelihood),
      impact: Number(values.impact),
      status: values.status,
      existing_controls: parseLineList(values.existing_controls),
      additional_controls: parseLineList(values.additional_controls),
      owner_user_id: values.owner_user_id ? Number(values.owner_user_id) : null,
      due_date: values.due_date || null,
      review_date: values.review_date || null,
      attachments_metadata: [],
      incident_id: values.incident_id ? Number(values.incident_id) : null,
    }),
  },
  inspections: {
    createTitle: 'Create Inspection',
    editTitle: 'Edit Inspection',
    description: 'Set up the inspection, then optionally add checklist lines in a compact format.',
    refs: ['sites', 'users'],
    fields: [
      { name: 'site_id', label: 'Site', type: 'select', required: true, optionsSource: 'sites' },
      baseTextField('title', 'Title', true),
      baseTextField('inspection_type', 'Inspection type', true),
      baseTextField('area_location', 'Area / location', true),
      { name: 'inspector_user_id', label: 'Inspector', type: 'select', required: true, optionsSource: 'users' },
      { name: 'inspection_date', label: 'Inspection date', type: 'datetime-local', required: true },
      {
        name: 'status',
        label: 'Status',
        type: 'select',
        required: true,
        options: buildSelectOptions(['draft', 'in_progress', 'completed', 'archived']),
      },
      { name: 'notes', label: 'Notes', type: 'textarea' },
      { name: 'findings_summary', label: 'Findings summary', type: 'textarea' },
      {
        name: 'checklist_items_text',
        label: 'Checklist items',
        type: 'textarea',
        helperText:
          'One line per item: item name | result | comment | linked hazard id | yes/no',
      },
      {
        name: 'linked_hazard_ids_text',
        label: 'Linked hazard IDs',
        type: 'textarea',
        helperText: 'Optional comma or newline separated hazard IDs.',
      },
    ],
    getInitialValues: (item, currentUser) => ({
      site_id: item?.site_id ? String(item.site_id) : '',
      title: item?.title ?? '',
      inspection_type: item?.inspection_type ?? 'workplace',
      area_location: item?.area_location ?? '',
      inspector_user_id: item?.inspector_user_id ? String(item.inspector_user_id) : String(currentUser?.id ?? ''),
      inspection_date:
        toLocalDateTimeInput(item?.inspection_date) || toLocalDateTimeInput(new Date().toISOString()),
      status: item?.status ?? 'draft',
      notes: item?.notes ?? '',
      findings_summary: item?.findings_summary ?? '',
      checklist_items_text: formatChecklistItems(item?.checklist_items),
      linked_hazard_ids_text: formatIdList(item?.linked_hazard_ids),
    }),
    validate(values) {
      const errors = {}
      if (!values.site_id) errors.site_id = 'Select a site.'
      if (!values.title || values.title.trim().length < 2) errors.title = 'Title is required.'
      if (!values.inspection_type || values.inspection_type.trim().length < 2) {
        errors.inspection_type = 'Inspection type is required.'
      }
      if (!values.area_location || values.area_location.trim().length < 2) {
        errors.area_location = 'Area / location is required.'
      }
      if (!values.inspector_user_id) errors.inspector_user_id = 'Select an inspector.'
      if (!values.inspection_date) errors.inspection_date = 'Inspection date is required.'
      return errors
    },
    buildPayload: (values) => ({
      site_id: Number(values.site_id),
      title: values.title.trim(),
      inspection_type: values.inspection_type.trim(),
      area_location: values.area_location.trim(),
      inspector_user_id: Number(values.inspector_user_id),
      inspection_date: toIsoDateTime(values.inspection_date),
      status: values.status,
      notes: values.notes.trim() || null,
      findings_summary: values.findings_summary.trim() || null,
      checklist_items: parseChecklistItems(values.checklist_items_text),
      attachments_metadata: [],
      linked_hazard_ids: parseIdList(values.linked_hazard_ids_text),
    }),
  },
  'corrective-actions': {
    createTitle: 'Create Corrective Action',
    editTitle: 'Edit Corrective Action',
    description: 'Assign a simple action and let the backend handle lifecycle rules.',
    refs: ['sites', 'users'],
    fields: [
      { name: 'site_id', label: 'Site', type: 'select', required: true, optionsSource: 'sites' },
      baseTextField('title', 'Title', true),
      { name: 'description', label: 'Description', type: 'textarea', required: true },
      {
        name: 'source_type',
        label: 'Source type',
        type: 'select',
        required: true,
        options: buildSelectOptions(['incident', 'hazard', 'inspection', 'manual']),
      },
      { name: 'source_id', label: 'Source ID', type: 'number' },
      { name: 'assigned_to_user_id', label: 'Assigned to', type: 'select', optionsSource: 'users' },
      {
        name: 'priority',
        label: 'Priority',
        type: 'select',
        required: true,
        options: buildSelectOptions(['low', 'medium', 'high', 'critical']),
      },
      {
        name: 'status',
        label: 'Status',
        type: 'select',
        required: true,
        options: buildSelectOptions([
          'open',
          'in_progress',
          'pending_verification',
          'closed',
          'overdue',
          'cancelled',
        ]),
      },
      { name: 'due_date', label: 'Due date', type: 'date' },
      { name: 'closure_notes', label: 'Closure notes', type: 'textarea' },
      { name: 'verification_notes', label: 'Verification notes', type: 'textarea' },
    ],
    getInitialValues: (item, currentUser) => ({
      site_id: item?.site_id ? String(item.site_id) : '',
      title: item?.title ?? '',
      description: item?.description ?? '',
      source_type: item?.source_type ?? 'manual',
      source_id: item?.source_id ? String(item.source_id) : '',
      assigned_to_user_id: item?.assigned_to_user_id
        ? String(item.assigned_to_user_id)
        : String(currentUser?.id ?? ''),
      priority: item?.priority ?? 'medium',
      status: item?.status ?? 'open',
      due_date: item?.due_date ?? '',
      closure_notes: item?.closure_notes ?? '',
      verification_notes: item?.verification_notes ?? '',
    }),
    validate(values) {
      const errors = {}
      if (!values.site_id) errors.site_id = 'Select a site.'
      if (!values.title || values.title.trim().length < 2) errors.title = 'Title is required.'
      if (!values.description || values.description.trim().length < 2) errors.description = 'Description is required.'
      if (values.source_type !== 'manual' && !values.source_id) {
        errors.source_id = 'Source ID is required unless this is a manual action.'
      }
      return errors
    },
    buildPayload: (values) => ({
      site_id: Number(values.site_id),
      title: values.title.trim(),
      description: values.description.trim(),
      source_type: values.source_type,
      source_id: values.source_id ? Number(values.source_id) : null,
      assigned_to_user_id: values.assigned_to_user_id
        ? Number(values.assigned_to_user_id)
        : null,
      created_by_user_id: null,
      priority: values.priority,
      status: values.status,
      due_date: values.due_date || null,
      closure_notes: values.closure_notes.trim() || null,
      closure_evidence_metadata: [],
      verification_notes: values.verification_notes.trim() || null,
      verified_by_user_id: null,
      verified_at: null,
      started_at: null,
      completed_at: null,
    }),
  },
  permits: {
    createTitle: 'Create Permit',
    editTitle: 'Edit Permit',
    description: 'Focus on the main permit details and leave the advanced evidence structures optional.',
    refs: ['sites', 'users'],
    fields: [
      baseTextField('permit_number', 'Permit number', true),
      {
        name: 'permit_type',
        label: 'Permit type',
        type: 'select',
        required: true,
        options: buildSelectOptions([
          'hot_work',
          'confined_space',
          'electrical',
          'work_at_height',
          'excavation',
          'lifting',
          'maintenance',
          'contractor',
        ]),
      },
      baseTextField('title', 'Title', true),
      { name: 'description', label: 'Description', type: 'textarea', required: true },
      { name: 'site_id', label: 'Site', type: 'select', required: true, optionsSource: 'sites' },
      baseTextField('area_location', 'Area / location', true),
      {
        name: 'requested_by_user_id',
        label: 'Requested by',
        type: 'select',
        required: true,
        optionsSource: 'users',
        visible: ({ user }) => canUseUserReferences(user),
      },
      {
        name: 'issued_by_user_id',
        label: 'Issued by',
        type: 'select',
        optionsSource: 'users',
        visible: ({ user }) => canUseUserReferences(user),
      },
      {
        name: 'approved_by_user_id',
        label: 'Approved by',
        type: 'select',
        optionsSource: 'users',
        visible: ({ user }) => canUseUserReferences(user),
      },
      { name: 'assigned_team_or_contractor', label: 'Team / contractor', type: 'text' },
      { name: 'start_datetime', label: 'Start', type: 'datetime-local', required: true },
      { name: 'end_datetime', label: 'End', type: 'datetime-local', required: true },
      {
        name: 'status',
        label: 'Status',
        type: 'select',
        required: true,
        options: buildSelectOptions([
          'draft',
          'pending_approval',
          'approved',
          'active',
          'suspended',
          'expired',
          'closed',
          'cancelled',
          'rejected',
        ]),
      },
      { name: 'risk_summary', label: 'Risk summary', type: 'textarea' },
      { name: 'precautions_required', label: 'Precautions required', type: 'textarea', helperText: 'One precaution per line.' },
      { name: 'ppe_required', label: 'PPE required', type: 'textarea', helperText: 'One PPE item per line.' },
      { name: 'isolation_required', label: 'Isolation required', type: 'checkbox' },
      { name: 'gas_test_required', label: 'Gas test required', type: 'checkbox' },
      {
        name: 'gas_test_results_text',
        label: 'Gas test results',
        type: 'textarea',
        helperText: 'One line per result: test name | result | tested by',
      },
      { name: 'emergency_controls', label: 'Emergency controls', type: 'textarea', helperText: 'One control per line.' },
      { name: 'closure_notes', label: 'Closure notes', type: 'textarea' },
    ],
    getInitialValues: (item, currentUser) => ({
      permit_number: item?.permit_number ?? '',
      permit_type: item?.permit_type ?? 'hot_work',
      title: item?.title ?? '',
      description: item?.description ?? '',
      site_id: item?.site_id ? String(item.site_id) : '',
      area_location: item?.area_location ?? '',
      requested_by_user_id: item?.requested_by_user_id
        ? String(item.requested_by_user_id)
        : String(currentUser?.id ?? ''),
      issued_by_user_id: item?.issued_by_user_id ? String(item.issued_by_user_id) : '',
      approved_by_user_id: item?.approved_by_user_id ? String(item.approved_by_user_id) : '',
      assigned_team_or_contractor: item?.assigned_team_or_contractor ?? '',
      start_datetime:
        toLocalDateTimeInput(item?.start_datetime) || toLocalDateTimeInput(new Date().toISOString()),
      end_datetime:
        toLocalDateTimeInput(item?.end_datetime) ||
        toLocalDateTimeInput(new Date(Date.now() + 4 * 60 * 60 * 1000).toISOString()),
      status: item?.status ?? 'pending_approval',
      risk_summary: item?.risk_summary ?? '',
      precautions_required: formatLineList(item?.precautions_required),
      ppe_required: formatLineList(item?.ppe_required),
      isolation_required: Boolean(item?.isolation_required),
      gas_test_required: Boolean(item?.gas_test_required),
      gas_test_results_text: formatGasTestResults(item?.gas_test_results),
      emergency_controls: formatLineList(item?.emergency_controls),
      closure_notes: item?.closure_notes ?? '',
    }),
    validate(values, { user }) {
      const errors = {}
      if (!values.permit_number || values.permit_number.trim().length < 2) {
        errors.permit_number = 'Permit number is required.'
      }
      if (!values.title || values.title.trim().length < 2) {
        errors.title = 'Title is required.'
      }
      if (!values.description || values.description.trim().length < 2) {
        errors.description = 'Description is required.'
      }
      if (!values.site_id) errors.site_id = 'Select a site.'
      if (!values.area_location || values.area_location.trim().length < 2) {
        errors.area_location = 'Area / location is required.'
      }
      if (canUseUserReferences(user) && !values.requested_by_user_id) {
        errors.requested_by_user_id = 'Select the requesting user.'
      }
      if (!values.start_datetime) errors.start_datetime = 'Start date and time is required.'
      if (!values.end_datetime) errors.end_datetime = 'End date and time is required.'
      if (
        values.start_datetime &&
        values.end_datetime &&
        new Date(values.start_datetime) >= new Date(values.end_datetime)
      ) {
        errors.end_datetime = 'End date and time must be after the start.'
      }
      if (
        values.permit_type === 'hot_work' &&
        parseLineList(values.precautions_required).length === 0
      ) {
        errors.precautions_required = 'Hot work permits require at least one precaution.'
      }
      if (
        values.permit_type === 'confined_space' &&
        values.gas_test_required &&
        parseGasTestResults(values.gas_test_results_text).length === 0
      ) {
        errors.gas_test_results_text =
          'Confined space permits with gas testing require at least one result.'
      }
      return errors
    },
    buildPayload: (values, { user }) => ({
      permit_number: values.permit_number.trim(),
      permit_type: values.permit_type,
      title: values.title.trim(),
      description: values.description.trim(),
      site_id: Number(values.site_id),
      area_location: values.area_location.trim(),
      requested_by_user_id: canUseUserReferences(user)
        ? Number(values.requested_by_user_id)
        : Number(user?.id),
      issued_by_user_id: values.issued_by_user_id ? Number(values.issued_by_user_id) : null,
      approved_by_user_id: values.approved_by_user_id
        ? Number(values.approved_by_user_id)
        : null,
      assigned_team_or_contractor: values.assigned_team_or_contractor.trim() || null,
      start_datetime: toIsoDateTime(values.start_datetime),
      end_datetime: toIsoDateTime(values.end_datetime),
      status: values.status,
      risk_summary: values.risk_summary.trim() || null,
      precautions_required: parseLineList(values.precautions_required),
      ppe_required: parseLineList(values.ppe_required),
      isolation_required: Boolean(values.isolation_required),
      gas_test_required: Boolean(values.gas_test_required),
      gas_test_results: parseGasTestResults(values.gas_test_results_text),
      emergency_controls: parseLineList(values.emergency_controls),
      closure_notes: values.closure_notes.trim() || null,
      closed_at: null,
      attachments_metadata: [],
    }),
  },
}
