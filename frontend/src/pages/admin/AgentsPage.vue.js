import { computed, onMounted, reactive, ref } from 'vue';
import { PlusOutlined } from '@ant-design/icons-vue';
import { bindKnowledgeBase, createAgent, listAgentKnowledgeBases, listAgents, listKnowledgeBases, listOrgUnits, unbindKnowledgeBase, updateAgent } from '../../api/admin';
import { formatDateTime } from '../../utils/format';
const loading = ref(false);
const error = ref(false);
const submitting = ref(false);
const items = ref([]);
const orgUnits = ref([]);
const modalVisible = ref(false);
const editingId = ref(null);
const emptyForm = () => ({
    code: '',
    name: '',
    description: '',
    owner_org_unit_id: '',
    runtime_type: 'DIFY',
    runtime_app_id: '',
    visibility: 'EXTERNAL',
    publish_status: 'DRAFT',
});
const form = reactive(emptyForm());
const runtimeOptions = [
    { label: 'Dify', value: 'DIFY' },
    { label: 'Custom', value: 'CUSTOM' },
];
const visibilityOptions = [
    { label: '外部可见', value: 'EXTERNAL' },
    { label: '仅内部', value: 'INTERNAL' },
    { label: '私有', value: 'PRIVATE' },
];
const publishStatusOptions = [
    { label: '草稿', value: 'DRAFT' },
    { label: '已发布', value: 'PUBLISHED' },
    { label: '已禁用', value: 'DISABLED' },
    { label: '已归档', value: 'ARCHIVED' },
];
const tablePagination = reactive({
    current: 1,
    pageSize: 10,
    pageSizeOptions: ['10', '20', '50'],
    showSizeChanger: true,
    size: 'small',
    showTotal: (t) => `共 ${t} 条`,
});
const orgOptions = computed(() => orgUnits.value.map(org => ({
    label: `${org.name}（${org.type}）`,
    value: org.id,
})));
const columns = [
    { title: '智能体', key: 'agent', width: 220 },
    { title: '用途说明', key: 'description', ellipsis: true },
    { title: '运行时', dataIndex: 'runtime_type', key: 'runtime_type', width: 90 },
    { title: '可见性', dataIndex: 'visibility', key: 'visibility', width: 100 },
    { title: '发布状态', key: 'publish_status', width: 100 },
    { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 170 },
    { title: '操作', key: 'action', width: 80 },
];
function statusColor(status) {
    const map = {
        PUBLISHED: 'success',
        DRAFT: 'processing',
        DISABLED: 'warning',
        ARCHIVED: 'default',
    };
    return map[status] ?? 'default';
}
function statusText(status) {
    const map = {
        PUBLISHED: '已发布',
        DRAFT: '草稿',
        DISABLED: '已禁用',
        ARCHIVED: '已归档',
    };
    return map[status] ?? status;
}
async function load() {
    loading.value = true;
    error.value = false;
    try {
        items.value = await listAgents();
        tablePagination.current = 1;
    }
    catch {
        error.value = true;
    }
    finally {
        loading.value = false;
    }
}
function onTableChange(p) {
    tablePagination.current = p.current;
    tablePagination.pageSize = p.pageSize;
}
async function loadOrgUnits() {
    try {
        orgUnits.value = await listOrgUnits();
    }
    catch {
        orgUnits.value = [];
    }
}
function filterOrgOption(input, option) {
    return String(option?.label ?? '').toLowerCase().includes(input.toLowerCase());
}
function openCreate() {
    editingId.value = null;
    Object.assign(form, emptyForm());
    boundKbs.value = [];
    selectedKbId.value = undefined;
    modalVisible.value = true;
}
function openEdit(agent) {
    editingId.value = agent.id;
    form.code = agent.code;
    form.name = agent.name;
    form.description = agent.description ?? '';
    form.owner_org_unit_id = agent.owner_org_unit_id;
    form.runtime_type = agent.runtime_type;
    form.runtime_app_id = agent.runtime_app_id ?? '';
    form.visibility = agent.visibility;
    form.publish_status = agent.publish_status;
    loadBindings(agent.id);
    modalVisible.value = true;
}
function resetForm() {
    Object.assign(form, emptyForm());
    editingId.value = null;
}
async function submit() {
    submitting.value = true;
    try {
        if (editingId.value) {
            const payload = {
                name: form.name,
                description: form.description || undefined,
                runtime_type: form.runtime_type,
                runtime_app_id: form.runtime_app_id || undefined,
                publish_status: form.publish_status,
                visibility: form.visibility,
            };
            await updateAgent(editingId.value, payload);
        }
        else {
            const payload = {
                code: form.code,
                name: form.name,
                description: form.description || undefined,
                owner_org_unit_id: form.owner_org_unit_id,
                runtime_type: form.runtime_type,
                runtime_app_id: form.runtime_app_id || undefined,
                visibility: form.visibility,
            };
            await createAgent(payload);
        }
        modalVisible.value = false;
        resetForm();
        await load();
    }
    catch {
        // 错误由 http.ts 统一处理
    }
    finally {
        submitting.value = false;
    }
}
// ── 知识库绑定 ──────────────────────────────
const availableKbs = ref([]);
const boundKbs = ref([]);
const selectedKbId = ref(undefined);
const bindPriority = ref(100);
const bindingLoading = ref(false);
async function loadAvailableKbs() {
    try {
        availableKbs.value = await listKnowledgeBases();
    }
    catch { /* 静默处理 */ }
}
async function loadBindings(agentId) {
    try {
        boundKbs.value = await listAgentKnowledgeBases(agentId);
    }
    catch {
        boundKbs.value = [];
    }
}
/** 获取 KB 名称（用于显示已绑定 KB 的 tag） */
function kbName(knowledgeBaseId) {
    return availableKbs.value.find(k => k.id === knowledgeBaseId)?.name ?? knowledgeBaseId;
}
async function bindKb() {
    if (!selectedKbId.value || !editingId.value)
        return;
    bindingLoading.value = true;
    try {
        await bindKnowledgeBase(editingId.value, selectedKbId.value, bindPriority.value);
        selectedKbId.value = undefined;
        bindPriority.value = 100;
        await loadBindings(editingId.value);
    }
    catch { /* 错误由 http.ts 处理 */ }
    finally {
        bindingLoading.value = false;
    }
}
async function unbindKb(knowledgeBaseId) {
    if (!editingId.value)
        return;
    bindingLoading.value = true;
    try {
        await unbindKnowledgeBase(editingId.value, knowledgeBaseId);
        await loadBindings(editingId.value);
    }
    catch { /* 错误由 http.ts 处理 */ }
    finally {
        bindingLoading.value = false;
    }
}
onMounted(() => { load(); loadAvailableKbs(); loadOrgUnits(); });
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['page-toolbar']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-block" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-toolbar" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "page-subtitle" },
});
const __VLS_0 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    type: "primary",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    type: "primary",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_4;
let __VLS_5;
let __VLS_6;
const __VLS_7 = {
    onClick: (__VLS_ctx.openCreate)
};
__VLS_3.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_3.slots;
    const __VLS_8 = {}.PlusOutlined;
    /** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({}));
    const __VLS_10 = __VLS_9({}, ...__VLS_functionalComponentArgsRest(__VLS_9));
}
var __VLS_3;
if (__VLS_ctx.error) {
    const __VLS_12 = {}.AResult;
    /** @type {[typeof __VLS_components.AResult, typeof __VLS_components.aResult, typeof __VLS_components.AResult, typeof __VLS_components.aResult, ]} */ ;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
        status: "error",
        title: "加载失败",
        subTitle: "无法获取 Agent 列表，请检查网络或管理员 Key",
    }));
    const __VLS_14 = __VLS_13({
        status: "error",
        title: "加载失败",
        subTitle: "无法获取 Agent 列表，请检查网络或管理员 Key",
    }, ...__VLS_functionalComponentArgsRest(__VLS_13));
    __VLS_15.slots.default;
    {
        const { extra: __VLS_thisSlot } = __VLS_15.slots;
        const __VLS_16 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
            ...{ 'onClick': {} },
            type: "primary",
        }));
        const __VLS_18 = __VLS_17({
            ...{ 'onClick': {} },
            type: "primary",
        }, ...__VLS_functionalComponentArgsRest(__VLS_17));
        let __VLS_20;
        let __VLS_21;
        let __VLS_22;
        const __VLS_23 = {
            onClick: (__VLS_ctx.load)
        };
        __VLS_19.slots.default;
        var __VLS_19;
    }
    var __VLS_15;
}
else if (__VLS_ctx.items.length === 0 && !__VLS_ctx.loading) {
    const __VLS_24 = {}.AEmpty;
    /** @type {[typeof __VLS_components.AEmpty, typeof __VLS_components.aEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
        description: "暂无 Agent，点击上方按钮创建",
        ...{ style: {} },
    }));
    const __VLS_26 = __VLS_25({
        description: "暂无 Agent，点击上方按钮创建",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
}
else {
    const __VLS_28 = {}.ATable;
    /** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
        ...{ 'onChange': {} },
        columns: (__VLS_ctx.columns),
        dataSource: (__VLS_ctx.items),
        loading: (__VLS_ctx.loading),
        pagination: (__VLS_ctx.tablePagination),
        rowKey: "id",
        size: "middle",
    }));
    const __VLS_30 = __VLS_29({
        ...{ 'onChange': {} },
        columns: (__VLS_ctx.columns),
        dataSource: (__VLS_ctx.items),
        loading: (__VLS_ctx.loading),
        pagination: (__VLS_ctx.tablePagination),
        rowKey: "id",
        size: "middle",
    }, ...__VLS_functionalComponentArgsRest(__VLS_29));
    let __VLS_32;
    let __VLS_33;
    let __VLS_34;
    const __VLS_35 = {
        onChange: (__VLS_ctx.onTableChange)
    };
    __VLS_31.slots.default;
    {
        const { bodyCell: __VLS_thisSlot } = __VLS_31.slots;
        const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
        if (column.key === 'publish_status') {
            const __VLS_36 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
                color: (__VLS_ctx.statusColor(record.publish_status)),
            }));
            const __VLS_38 = __VLS_37({
                color: (__VLS_ctx.statusColor(record.publish_status)),
            }, ...__VLS_functionalComponentArgsRest(__VLS_37));
            __VLS_39.slots.default;
            (__VLS_ctx.statusText(record.publish_status));
            var __VLS_39;
        }
        if (column.key === 'agent') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "primary-cell" },
            });
            (record.name);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "secondary-cell" },
            });
            (record.code);
        }
        if (column.key === 'description') {
            (record.description || '-');
        }
        if (column.key === 'updated_at') {
            (__VLS_ctx.formatDateTime(record.updated_at));
        }
        if (column.key === 'action') {
            const __VLS_40 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }));
            const __VLS_42 = __VLS_41({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_41));
            let __VLS_44;
            let __VLS_45;
            let __VLS_46;
            const __VLS_47 = {
                onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.error))
                        return;
                    if (!!(__VLS_ctx.items.length === 0 && !__VLS_ctx.loading))
                        return;
                    if (!(column.key === 'action'))
                        return;
                    __VLS_ctx.openEdit(record);
                }
            };
            __VLS_43.slots.default;
            var __VLS_43;
        }
    }
    var __VLS_31;
}
const __VLS_48 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    open: (__VLS_ctx.modalVisible),
    title: (__VLS_ctx.editingId ? '编辑 Agent' : '新建 Agent'),
    confirmLoading: (__VLS_ctx.submitting),
    destroyOnClose: true,
}));
const __VLS_50 = __VLS_49({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    open: (__VLS_ctx.modalVisible),
    title: (__VLS_ctx.editingId ? '编辑 Agent' : '新建 Agent'),
    confirmLoading: (__VLS_ctx.submitting),
    destroyOnClose: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
let __VLS_52;
let __VLS_53;
let __VLS_54;
const __VLS_55 = {
    onOk: (__VLS_ctx.submit)
};
const __VLS_56 = {
    onCancel: (__VLS_ctx.resetForm)
};
__VLS_51.slots.default;
const __VLS_57 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_58 = __VLS_asFunctionalComponent(__VLS_57, new __VLS_57({
    model: (__VLS_ctx.form),
    layout: "vertical",
}));
const __VLS_59 = __VLS_58({
    model: (__VLS_ctx.form),
    layout: "vertical",
}, ...__VLS_functionalComponentArgsRest(__VLS_58));
__VLS_60.slots.default;
const __VLS_61 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_62 = __VLS_asFunctionalComponent(__VLS_61, new __VLS_61({
    label: "编码 (code)",
    required: true,
}));
const __VLS_63 = __VLS_62({
    label: "编码 (code)",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_62));
__VLS_64.slots.default;
const __VLS_65 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_66 = __VLS_asFunctionalComponent(__VLS_65, new __VLS_65({
    value: (__VLS_ctx.form.code),
    disabled: (!!__VLS_ctx.editingId),
    placeholder: "唯一标识，如 qa-agent",
}));
const __VLS_67 = __VLS_66({
    value: (__VLS_ctx.form.code),
    disabled: (!!__VLS_ctx.editingId),
    placeholder: "唯一标识，如 qa-agent",
}, ...__VLS_functionalComponentArgsRest(__VLS_66));
var __VLS_64;
const __VLS_69 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_70 = __VLS_asFunctionalComponent(__VLS_69, new __VLS_69({
    label: "名称",
    required: true,
}));
const __VLS_71 = __VLS_70({
    label: "名称",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_70));
__VLS_72.slots.default;
const __VLS_73 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_74 = __VLS_asFunctionalComponent(__VLS_73, new __VLS_73({
    value: (__VLS_ctx.form.name),
    placeholder: "Agent 显示名称",
}));
const __VLS_75 = __VLS_74({
    value: (__VLS_ctx.form.name),
    placeholder: "Agent 显示名称",
}, ...__VLS_functionalComponentArgsRest(__VLS_74));
var __VLS_72;
const __VLS_77 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_78 = __VLS_asFunctionalComponent(__VLS_77, new __VLS_77({
    label: "描述",
}));
const __VLS_79 = __VLS_78({
    label: "描述",
}, ...__VLS_functionalComponentArgsRest(__VLS_78));
__VLS_80.slots.default;
const __VLS_81 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_82 = __VLS_asFunctionalComponent(__VLS_81, new __VLS_81({
    value: (__VLS_ctx.form.description),
    rows: (2),
    placeholder: "简要描述 Agent 的功能",
}));
const __VLS_83 = __VLS_82({
    value: (__VLS_ctx.form.description),
    rows: (2),
    placeholder: "简要描述 Agent 的功能",
}, ...__VLS_functionalComponentArgsRest(__VLS_82));
var __VLS_80;
const __VLS_85 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_86 = __VLS_asFunctionalComponent(__VLS_85, new __VLS_85({
    label: "所属组织",
    required: true,
}));
const __VLS_87 = __VLS_86({
    label: "所属组织",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_86));
__VLS_88.slots.default;
const __VLS_89 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_90 = __VLS_asFunctionalComponent(__VLS_89, new __VLS_89({
    value: (__VLS_ctx.form.owner_org_unit_id),
    placeholder: "选择所属组织",
    showSearch: true,
    filterOption: (__VLS_ctx.filterOrgOption),
    options: (__VLS_ctx.orgOptions),
}));
const __VLS_91 = __VLS_90({
    value: (__VLS_ctx.form.owner_org_unit_id),
    placeholder: "选择所属组织",
    showSearch: true,
    filterOption: (__VLS_ctx.filterOrgOption),
    options: (__VLS_ctx.orgOptions),
}, ...__VLS_functionalComponentArgsRest(__VLS_90));
var __VLS_88;
const __VLS_93 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_94 = __VLS_asFunctionalComponent(__VLS_93, new __VLS_93({
    gutter: (16),
}));
const __VLS_95 = __VLS_94({
    gutter: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_94));
__VLS_96.slots.default;
const __VLS_97 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_98 = __VLS_asFunctionalComponent(__VLS_97, new __VLS_97({
    span: (12),
}));
const __VLS_99 = __VLS_98({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_98));
__VLS_100.slots.default;
const __VLS_101 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_102 = __VLS_asFunctionalComponent(__VLS_101, new __VLS_101({
    label: "运行时类型",
}));
const __VLS_103 = __VLS_102({
    label: "运行时类型",
}, ...__VLS_functionalComponentArgsRest(__VLS_102));
__VLS_104.slots.default;
const __VLS_105 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_106 = __VLS_asFunctionalComponent(__VLS_105, new __VLS_105({
    value: (__VLS_ctx.form.runtime_type),
    options: (__VLS_ctx.runtimeOptions),
}));
const __VLS_107 = __VLS_106({
    value: (__VLS_ctx.form.runtime_type),
    options: (__VLS_ctx.runtimeOptions),
}, ...__VLS_functionalComponentArgsRest(__VLS_106));
var __VLS_104;
var __VLS_100;
const __VLS_109 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_110 = __VLS_asFunctionalComponent(__VLS_109, new __VLS_109({
    span: (12),
}));
const __VLS_111 = __VLS_110({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_110));
__VLS_112.slots.default;
const __VLS_113 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_114 = __VLS_asFunctionalComponent(__VLS_113, new __VLS_113({
    label: "可见性",
}));
const __VLS_115 = __VLS_114({
    label: "可见性",
}, ...__VLS_functionalComponentArgsRest(__VLS_114));
__VLS_116.slots.default;
const __VLS_117 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_118 = __VLS_asFunctionalComponent(__VLS_117, new __VLS_117({
    value: (__VLS_ctx.form.visibility),
    options: (__VLS_ctx.visibilityOptions),
}));
const __VLS_119 = __VLS_118({
    value: (__VLS_ctx.form.visibility),
    options: (__VLS_ctx.visibilityOptions),
}, ...__VLS_functionalComponentArgsRest(__VLS_118));
var __VLS_116;
var __VLS_112;
var __VLS_96;
const __VLS_121 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_122 = __VLS_asFunctionalComponent(__VLS_121, new __VLS_121({
    label: "Dify App ID",
}));
const __VLS_123 = __VLS_122({
    label: "Dify App ID",
}, ...__VLS_functionalComponentArgsRest(__VLS_122));
__VLS_124.slots.default;
const __VLS_125 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_126 = __VLS_asFunctionalComponent(__VLS_125, new __VLS_125({
    value: (__VLS_ctx.form.runtime_app_id),
    placeholder: "Dify 应用的 App ID",
}));
const __VLS_127 = __VLS_126({
    value: (__VLS_ctx.form.runtime_app_id),
    placeholder: "Dify 应用的 App ID",
}, ...__VLS_functionalComponentArgsRest(__VLS_126));
var __VLS_124;
if (!__VLS_ctx.editingId) {
    const __VLS_129 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_130 = __VLS_asFunctionalComponent(__VLS_129, new __VLS_129({
        label: "发布状态",
    }));
    const __VLS_131 = __VLS_130({
        label: "发布状态",
    }, ...__VLS_functionalComponentArgsRest(__VLS_130));
    __VLS_132.slots.default;
    const __VLS_133 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_134 = __VLS_asFunctionalComponent(__VLS_133, new __VLS_133({
        value: (__VLS_ctx.form.publish_status),
        options: (__VLS_ctx.publishStatusOptions),
    }));
    const __VLS_135 = __VLS_134({
        value: (__VLS_ctx.form.publish_status),
        options: (__VLS_ctx.publishStatusOptions),
    }, ...__VLS_functionalComponentArgsRest(__VLS_134));
    var __VLS_132;
}
if (__VLS_ctx.editingId) {
    const __VLS_137 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_138 = __VLS_asFunctionalComponent(__VLS_137, new __VLS_137({
        label: "发布状态",
    }));
    const __VLS_139 = __VLS_138({
        label: "发布状态",
    }, ...__VLS_functionalComponentArgsRest(__VLS_138));
    __VLS_140.slots.default;
    const __VLS_141 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_142 = __VLS_asFunctionalComponent(__VLS_141, new __VLS_141({
        value: (__VLS_ctx.form.publish_status),
        options: (__VLS_ctx.publishStatusOptions),
    }));
    const __VLS_143 = __VLS_142({
        value: (__VLS_ctx.form.publish_status),
        options: (__VLS_ctx.publishStatusOptions),
    }, ...__VLS_functionalComponentArgsRest(__VLS_142));
    var __VLS_140;
}
if (__VLS_ctx.editingId) {
    const __VLS_145 = {}.ADivider;
    /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
    // @ts-ignore
    const __VLS_146 = __VLS_asFunctionalComponent(__VLS_145, new __VLS_145({
        orientation: "left",
        ...{ style: {} },
    }));
    const __VLS_147 = __VLS_146({
        orientation: "left",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_146));
    __VLS_148.slots.default;
    var __VLS_148;
}
if (__VLS_ctx.editingId) {
    const __VLS_149 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_150 = __VLS_asFunctionalComponent(__VLS_149, new __VLS_149({
        label: "已绑定 KB",
    }));
    const __VLS_151 = __VLS_150({
        label: "已绑定 KB",
    }, ...__VLS_functionalComponentArgsRest(__VLS_150));
    __VLS_152.slots.default;
    const __VLS_153 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_154 = __VLS_asFunctionalComponent(__VLS_153, new __VLS_153({
        wrap: true,
    }));
    const __VLS_155 = __VLS_154({
        wrap: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_154));
    __VLS_156.slots.default;
    for (const [b] of __VLS_getVForSourceType((__VLS_ctx.boundKbs))) {
        const __VLS_157 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_158 = __VLS_asFunctionalComponent(__VLS_157, new __VLS_157({
            ...{ 'onClose': {} },
            key: (b.knowledge_base_id),
            closable: true,
        }));
        const __VLS_159 = __VLS_158({
            ...{ 'onClose': {} },
            key: (b.knowledge_base_id),
            closable: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_158));
        let __VLS_161;
        let __VLS_162;
        let __VLS_163;
        const __VLS_164 = {
            onClose: (...[$event]) => {
                if (!(__VLS_ctx.editingId))
                    return;
                __VLS_ctx.unbindKb(b.knowledge_base_id);
            }
        };
        __VLS_160.slots.default;
        (__VLS_ctx.kbName(b.knowledge_base_id));
        if (b.priority !== 100) {
            (b.priority);
        }
        var __VLS_160;
    }
    if (__VLS_ctx.boundKbs.length === 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ style: {} },
        });
    }
    var __VLS_156;
    var __VLS_152;
}
if (__VLS_ctx.editingId) {
    const __VLS_165 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_166 = __VLS_asFunctionalComponent(__VLS_165, new __VLS_165({
        label: "添加绑定",
    }));
    const __VLS_167 = __VLS_166({
        label: "添加绑定",
    }, ...__VLS_functionalComponentArgsRest(__VLS_166));
    __VLS_168.slots.default;
    const __VLS_169 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_170 = __VLS_asFunctionalComponent(__VLS_169, new __VLS_169({}));
    const __VLS_171 = __VLS_170({}, ...__VLS_functionalComponentArgsRest(__VLS_170));
    __VLS_172.slots.default;
    const __VLS_173 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_174 = __VLS_asFunctionalComponent(__VLS_173, new __VLS_173({
        value: (__VLS_ctx.selectedKbId),
        placeholder: "选择知识库",
        ...{ style: {} },
        showSearch: true,
        filterOption: ((input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())),
        options: (__VLS_ctx.availableKbs
            .filter(k => !__VLS_ctx.boundKbs.some(b => b.knowledge_base_id === k.id))
            .map(k => ({ label: k.name, value: k.id }))),
    }));
    const __VLS_175 = __VLS_174({
        value: (__VLS_ctx.selectedKbId),
        placeholder: "选择知识库",
        ...{ style: {} },
        showSearch: true,
        filterOption: ((input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())),
        options: (__VLS_ctx.availableKbs
            .filter(k => !__VLS_ctx.boundKbs.some(b => b.knowledge_base_id === k.id))
            .map(k => ({ label: k.name, value: k.id }))),
    }, ...__VLS_functionalComponentArgsRest(__VLS_174));
    const __VLS_177 = {}.AInputNumber;
    /** @type {[typeof __VLS_components.AInputNumber, typeof __VLS_components.aInputNumber, ]} */ ;
    // @ts-ignore
    const __VLS_178 = __VLS_asFunctionalComponent(__VLS_177, new __VLS_177({
        value: (__VLS_ctx.bindPriority),
        min: (1),
        max: (999),
        ...{ style: {} },
        placeholder: "优先级",
    }));
    const __VLS_179 = __VLS_178({
        value: (__VLS_ctx.bindPriority),
        min: (1),
        max: (999),
        ...{ style: {} },
        placeholder: "优先级",
    }, ...__VLS_functionalComponentArgsRest(__VLS_178));
    const __VLS_181 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_182 = __VLS_asFunctionalComponent(__VLS_181, new __VLS_181({
        ...{ 'onClick': {} },
        type: "primary",
        size: "small",
        loading: (__VLS_ctx.bindingLoading),
        disabled: (!__VLS_ctx.selectedKbId),
    }));
    const __VLS_183 = __VLS_182({
        ...{ 'onClick': {} },
        type: "primary",
        size: "small",
        loading: (__VLS_ctx.bindingLoading),
        disabled: (!__VLS_ctx.selectedKbId),
    }, ...__VLS_functionalComponentArgsRest(__VLS_182));
    let __VLS_185;
    let __VLS_186;
    let __VLS_187;
    const __VLS_188 = {
        onClick: (__VLS_ctx.bindKb)
    };
    __VLS_184.slots.default;
    var __VLS_184;
    var __VLS_172;
    var __VLS_168;
}
var __VLS_60;
var __VLS_51;
/** @type {__VLS_StyleScopedClasses['page-block']} */ ;
/** @type {__VLS_StyleScopedClasses['page-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['page-subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['primary-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['secondary-cell']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            PlusOutlined: PlusOutlined,
            formatDateTime: formatDateTime,
            loading: loading,
            error: error,
            submitting: submitting,
            items: items,
            modalVisible: modalVisible,
            editingId: editingId,
            form: form,
            runtimeOptions: runtimeOptions,
            visibilityOptions: visibilityOptions,
            publishStatusOptions: publishStatusOptions,
            tablePagination: tablePagination,
            orgOptions: orgOptions,
            columns: columns,
            statusColor: statusColor,
            statusText: statusText,
            load: load,
            onTableChange: onTableChange,
            filterOrgOption: filterOrgOption,
            openCreate: openCreate,
            openEdit: openEdit,
            resetForm: resetForm,
            submit: submit,
            availableKbs: availableKbs,
            boundKbs: boundKbs,
            selectedKbId: selectedKbId,
            bindPriority: bindPriority,
            bindingLoading: bindingLoading,
            kbName: kbName,
            bindKb: bindKb,
            unbindKb: unbindKb,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
