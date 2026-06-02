import { computed, onMounted, reactive, ref } from 'vue';
import { FileAddOutlined, PlusOutlined } from '@ant-design/icons-vue';
import { createDocument, createKnowledgeBase, listDocuments, listKnowledgeBases, listOrgUnits, } from '../../api/admin';
import { formatDateTime } from '../../utils/format';
// ---- 知识库 ----
const kbLoading = ref(false);
const kbError = ref(false);
const kbs = ref([]);
const orgUnits = ref([]);
const kbModalVisible = ref(false);
const kbForm = reactive({ name: '', owner_org_unit_id: '', provider: 'DIFY', provider_kb_id: '', embedding_model: '' });
const providerOptions = [
    { label: 'Dify', value: 'DIFY' },
    { label: 'Custom', value: 'CUSTOM' },
];
function createTablePagination() {
    return {
        current: 1,
        pageSize: 10,
        pageSizeOptions: ['10', '20', '50'],
        showSizeChanger: true,
        size: 'small',
        showTotal: (t) => `共 ${t} 条`,
    };
}
const kbPagination = reactive(createTablePagination());
const docPagination = reactive(createTablePagination());
function onKbTableChange(p) {
    kbPagination.current = p.current;
    kbPagination.pageSize = p.pageSize;
}
function onDocTableChange(p) {
    docPagination.current = p.current;
    docPagination.pageSize = p.pageSize;
}
const orgOptions = computed(() => orgUnits.value.map(org => ({
    label: `${org.name}（${org.type}）`,
    value: org.id,
})));
const kbColumns = [
    { title: '知识库', key: 'kb' },
    { title: '状态', key: 'status', width: 90 },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
];
// ---- 文档 ----
const docLoading = ref(false);
const docError = ref(false);
const docs = ref([]);
const docModalVisible = ref(false);
const docForm = reactive({
    knowledge_base_id: '',
    owner_org_unit_id: '',
    file_name: '',
    provider_doc_id: '',
    storage_uri: '',
});
const docColumns = [
    { title: '文件名', dataIndex: 'file_name', key: 'file_name' },
    { title: '文件类型', dataIndex: 'file_type', key: 'file_type', width: 100 },
    { title: '解析状态', key: 'parse_status', width: 100 },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
];
// ---- tabs / submit ----
const activeTab = ref('kb');
const submitting = ref(false);
function parseColor(status) {
    const map = { COMPLETED: 'success', PENDING: 'default', PARSING: 'processing', FAILED: 'error' };
    return map[status] ?? 'default';
}
async function loadKBs() {
    kbLoading.value = true;
    kbError.value = false;
    try {
        kbs.value = await listKnowledgeBases();
    }
    catch {
        kbError.value = true;
    }
    finally {
        kbLoading.value = false;
    }
}
async function loadDocs() {
    docLoading.value = true;
    docError.value = false;
    try {
        docs.value = await listDocuments();
    }
    catch {
        docError.value = true;
    }
    finally {
        docLoading.value = false;
    }
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
function openCreateKB() {
    Object.assign(kbForm, { name: '', owner_org_unit_id: '', provider: 'DIFY', provider_kb_id: '', embedding_model: '' });
    kbModalVisible.value = true;
}
async function submitKB() {
    submitting.value = true;
    try {
        const payload = {
            name: kbForm.name,
            owner_org_unit_id: kbForm.owner_org_unit_id,
            provider: kbForm.provider,
            provider_kb_id: kbForm.provider_kb_id || undefined,
            embedding_model: kbForm.embedding_model || undefined,
        };
        await createKnowledgeBase(payload);
        kbModalVisible.value = false;
        await loadKBs();
    }
    catch { /* */ }
    finally {
        submitting.value = false;
    }
}
function openCreateDoc() {
    Object.assign(docForm, { knowledge_base_id: '', owner_org_unit_id: '', file_name: '', provider_doc_id: '', storage_uri: '' });
    docModalVisible.value = true;
}
async function submitDoc() {
    submitting.value = true;
    try {
        await createDocument({
            knowledge_base_id: docForm.knowledge_base_id,
            owner_org_unit_id: docForm.owner_org_unit_id,
            file_name: docForm.file_name,
            provider_doc_id: docForm.provider_doc_id || undefined,
            storage_uri: docForm.storage_uri || undefined,
        });
        docModalVisible.value = false;
        await loadDocs();
    }
    catch { /* */ }
    finally {
        submitting.value = false;
    }
}
onMounted(() => {
    loadKBs();
    loadDocs();
    loadOrgUnits();
});
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
const __VLS_0 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ 'onClick': {} },
}));
const __VLS_6 = __VLS_5({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
let __VLS_8;
let __VLS_9;
let __VLS_10;
const __VLS_11 = {
    onClick: (__VLS_ctx.openCreateKB)
};
__VLS_7.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_7.slots;
    const __VLS_12 = {}.PlusOutlined;
    /** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({}));
    const __VLS_14 = __VLS_13({}, ...__VLS_functionalComponentArgsRest(__VLS_13));
}
var __VLS_7;
const __VLS_16 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    ...{ 'onClick': {} },
}));
const __VLS_18 = __VLS_17({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
let __VLS_20;
let __VLS_21;
let __VLS_22;
const __VLS_23 = {
    onClick: (__VLS_ctx.openCreateDoc)
};
__VLS_19.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_19.slots;
    const __VLS_24 = {}.FileAddOutlined;
    /** @type {[typeof __VLS_components.FileAddOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({}));
    const __VLS_26 = __VLS_25({}, ...__VLS_functionalComponentArgsRest(__VLS_25));
}
var __VLS_19;
var __VLS_3;
const __VLS_28 = {}.ATabs;
/** @type {[typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    activeKey: (__VLS_ctx.activeTab),
}));
const __VLS_30 = __VLS_29({
    activeKey: (__VLS_ctx.activeTab),
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
const __VLS_32 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    key: "kb",
    tab: "知识库",
}));
const __VLS_34 = __VLS_33({
    key: "kb",
    tab: "知识库",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_35.slots.default;
if (__VLS_ctx.kbError) {
    const __VLS_36 = {}.AResult;
    /** @type {[typeof __VLS_components.AResult, typeof __VLS_components.aResult, typeof __VLS_components.AResult, typeof __VLS_components.aResult, ]} */ ;
    // @ts-ignore
    const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
        status: "error",
        title: "加载失败",
        subTitle: "无法获取知识库列表",
    }));
    const __VLS_38 = __VLS_37({
        status: "error",
        title: "加载失败",
        subTitle: "无法获取知识库列表",
    }, ...__VLS_functionalComponentArgsRest(__VLS_37));
    __VLS_39.slots.default;
    {
        const { extra: __VLS_thisSlot } = __VLS_39.slots;
        const __VLS_40 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
            ...{ 'onClick': {} },
            type: "primary",
        }));
        const __VLS_42 = __VLS_41({
            ...{ 'onClick': {} },
            type: "primary",
        }, ...__VLS_functionalComponentArgsRest(__VLS_41));
        let __VLS_44;
        let __VLS_45;
        let __VLS_46;
        const __VLS_47 = {
            onClick: (__VLS_ctx.loadKBs)
        };
        __VLS_43.slots.default;
        var __VLS_43;
    }
    var __VLS_39;
}
else if (__VLS_ctx.kbs.length === 0 && !__VLS_ctx.kbLoading) {
    const __VLS_48 = {}.AEmpty;
    /** @type {[typeof __VLS_components.AEmpty, typeof __VLS_components.aEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
        description: "暂无可用知识库",
        ...{ style: {} },
    }));
    const __VLS_50 = __VLS_49({
        description: "暂无可用知识库",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_49));
}
else {
    const __VLS_52 = {}.ATable;
    /** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
        ...{ 'onChange': {} },
        columns: (__VLS_ctx.kbColumns),
        dataSource: (__VLS_ctx.kbs),
        loading: (__VLS_ctx.kbLoading),
        pagination: (__VLS_ctx.kbPagination),
        rowKey: "id",
        size: "middle",
    }));
    const __VLS_54 = __VLS_53({
        ...{ 'onChange': {} },
        columns: (__VLS_ctx.kbColumns),
        dataSource: (__VLS_ctx.kbs),
        loading: (__VLS_ctx.kbLoading),
        pagination: (__VLS_ctx.kbPagination),
        rowKey: "id",
        size: "middle",
    }, ...__VLS_functionalComponentArgsRest(__VLS_53));
    let __VLS_56;
    let __VLS_57;
    let __VLS_58;
    const __VLS_59 = {
        onChange: (__VLS_ctx.onKbTableChange)
    };
    __VLS_55.slots.default;
    {
        const { bodyCell: __VLS_thisSlot } = __VLS_55.slots;
        const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
        if (column.key === 'status') {
            const __VLS_60 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
                color: (record.status === 'ACTIVE' ? 'green' : 'default'),
            }));
            const __VLS_62 = __VLS_61({
                color: (record.status === 'ACTIVE' ? 'green' : 'default'),
            }, ...__VLS_functionalComponentArgsRest(__VLS_61));
            __VLS_63.slots.default;
            (record.status === 'ACTIVE' ? '启用' : record.status);
            var __VLS_63;
        }
        if (column.key === 'kb') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "primary-cell" },
            });
            (record.name);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "secondary-cell" },
            });
            (record.provider);
        }
        if (column.key === 'created_at') {
            (__VLS_ctx.formatDateTime(record.created_at));
        }
    }
    var __VLS_55;
}
var __VLS_35;
const __VLS_64 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    key: "doc",
    tab: "文档",
}));
const __VLS_66 = __VLS_65({
    key: "doc",
    tab: "文档",
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
__VLS_67.slots.default;
if (__VLS_ctx.docError) {
    const __VLS_68 = {}.AResult;
    /** @type {[typeof __VLS_components.AResult, typeof __VLS_components.aResult, typeof __VLS_components.AResult, typeof __VLS_components.aResult, ]} */ ;
    // @ts-ignore
    const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
        status: "error",
        title: "加载失败",
        subTitle: "无法获取文档列表",
    }));
    const __VLS_70 = __VLS_69({
        status: "error",
        title: "加载失败",
        subTitle: "无法获取文档列表",
    }, ...__VLS_functionalComponentArgsRest(__VLS_69));
    __VLS_71.slots.default;
    {
        const { extra: __VLS_thisSlot } = __VLS_71.slots;
        const __VLS_72 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
            ...{ 'onClick': {} },
            type: "primary",
        }));
        const __VLS_74 = __VLS_73({
            ...{ 'onClick': {} },
            type: "primary",
        }, ...__VLS_functionalComponentArgsRest(__VLS_73));
        let __VLS_76;
        let __VLS_77;
        let __VLS_78;
        const __VLS_79 = {
            onClick: (__VLS_ctx.loadDocs)
        };
        __VLS_75.slots.default;
        var __VLS_75;
    }
    var __VLS_71;
}
else if (__VLS_ctx.docs.length === 0 && !__VLS_ctx.docLoading) {
    const __VLS_80 = {}.AEmpty;
    /** @type {[typeof __VLS_components.AEmpty, typeof __VLS_components.aEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
        description: "暂无已接入文档",
        ...{ style: {} },
    }));
    const __VLS_82 = __VLS_81({
        description: "暂无已接入文档",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
}
else {
    const __VLS_84 = {}.ATable;
    /** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
    // @ts-ignore
    const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
        ...{ 'onChange': {} },
        columns: (__VLS_ctx.docColumns),
        dataSource: (__VLS_ctx.docs),
        loading: (__VLS_ctx.docLoading),
        pagination: (__VLS_ctx.docPagination),
        rowKey: "id",
        size: "middle",
    }));
    const __VLS_86 = __VLS_85({
        ...{ 'onChange': {} },
        columns: (__VLS_ctx.docColumns),
        dataSource: (__VLS_ctx.docs),
        loading: (__VLS_ctx.docLoading),
        pagination: (__VLS_ctx.docPagination),
        rowKey: "id",
        size: "middle",
    }, ...__VLS_functionalComponentArgsRest(__VLS_85));
    let __VLS_88;
    let __VLS_89;
    let __VLS_90;
    const __VLS_91 = {
        onChange: (__VLS_ctx.onDocTableChange)
    };
    __VLS_87.slots.default;
    {
        const { bodyCell: __VLS_thisSlot } = __VLS_87.slots;
        const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
        if (column.key === 'parse_status') {
            const __VLS_92 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
                color: (__VLS_ctx.parseColor(record.parse_status)),
            }));
            const __VLS_94 = __VLS_93({
                color: (__VLS_ctx.parseColor(record.parse_status)),
            }, ...__VLS_functionalComponentArgsRest(__VLS_93));
            __VLS_95.slots.default;
            (record.parse_status);
            var __VLS_95;
        }
        if (column.key === 'created_at') {
            (__VLS_ctx.formatDateTime(record.created_at));
        }
    }
    var __VLS_87;
}
var __VLS_67;
var __VLS_31;
const __VLS_96 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
    ...{ 'onOk': {} },
    open: (__VLS_ctx.kbModalVisible),
    title: "新建知识库",
    confirmLoading: (__VLS_ctx.submitting),
    destroyOnClose: true,
}));
const __VLS_98 = __VLS_97({
    ...{ 'onOk': {} },
    open: (__VLS_ctx.kbModalVisible),
    title: "新建知识库",
    confirmLoading: (__VLS_ctx.submitting),
    destroyOnClose: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_97));
let __VLS_100;
let __VLS_101;
let __VLS_102;
const __VLS_103 = {
    onOk: (__VLS_ctx.submitKB)
};
__VLS_99.slots.default;
const __VLS_104 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
    layout: "vertical",
}));
const __VLS_106 = __VLS_105({
    layout: "vertical",
}, ...__VLS_functionalComponentArgsRest(__VLS_105));
__VLS_107.slots.default;
const __VLS_108 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
    label: "名称",
    required: true,
}));
const __VLS_110 = __VLS_109({
    label: "名称",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_109));
__VLS_111.slots.default;
const __VLS_112 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
    value: (__VLS_ctx.kbForm.name),
    placeholder: "知识库名称",
}));
const __VLS_114 = __VLS_113({
    value: (__VLS_ctx.kbForm.name),
    placeholder: "知识库名称",
}, ...__VLS_functionalComponentArgsRest(__VLS_113));
var __VLS_111;
const __VLS_116 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
    label: "所属组织",
    required: true,
}));
const __VLS_118 = __VLS_117({
    label: "所属组织",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_117));
__VLS_119.slots.default;
const __VLS_120 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
    value: (__VLS_ctx.kbForm.owner_org_unit_id),
    placeholder: "选择所属组织",
    showSearch: true,
    filterOption: (__VLS_ctx.filterOrgOption),
    options: (__VLS_ctx.orgOptions),
    ...{ class: "modal-select" },
    ...{ style: {} },
}));
const __VLS_122 = __VLS_121({
    value: (__VLS_ctx.kbForm.owner_org_unit_id),
    placeholder: "选择所属组织",
    showSearch: true,
    filterOption: (__VLS_ctx.filterOrgOption),
    options: (__VLS_ctx.orgOptions),
    ...{ class: "modal-select" },
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_121));
var __VLS_119;
const __VLS_124 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
    label: "提供方",
}));
const __VLS_126 = __VLS_125({
    label: "提供方",
}, ...__VLS_functionalComponentArgsRest(__VLS_125));
__VLS_127.slots.default;
const __VLS_128 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
    value: (__VLS_ctx.kbForm.provider),
    options: (__VLS_ctx.providerOptions),
    ...{ class: "modal-select" },
    ...{ style: {} },
}));
const __VLS_130 = __VLS_129({
    value: (__VLS_ctx.kbForm.provider),
    options: (__VLS_ctx.providerOptions),
    ...{ class: "modal-select" },
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_129));
var __VLS_127;
const __VLS_132 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
    label: "Provider KB ID",
}));
const __VLS_134 = __VLS_133({
    label: "Provider KB ID",
}, ...__VLS_functionalComponentArgsRest(__VLS_133));
__VLS_135.slots.default;
const __VLS_136 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
    value: (__VLS_ctx.kbForm.provider_kb_id),
    placeholder: "Dify 知识库的 dataset_id",
}));
const __VLS_138 = __VLS_137({
    value: (__VLS_ctx.kbForm.provider_kb_id),
    placeholder: "Dify 知识库的 dataset_id",
}, ...__VLS_functionalComponentArgsRest(__VLS_137));
var __VLS_135;
const __VLS_140 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
    label: "Embedding 模型",
}));
const __VLS_142 = __VLS_141({
    label: "Embedding 模型",
}, ...__VLS_functionalComponentArgsRest(__VLS_141));
__VLS_143.slots.default;
const __VLS_144 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
    value: (__VLS_ctx.kbForm.embedding_model),
    placeholder: "如 text-embedding-ada-002",
}));
const __VLS_146 = __VLS_145({
    value: (__VLS_ctx.kbForm.embedding_model),
    placeholder: "如 text-embedding-ada-002",
}, ...__VLS_functionalComponentArgsRest(__VLS_145));
var __VLS_143;
var __VLS_107;
var __VLS_99;
const __VLS_148 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
    ...{ 'onOk': {} },
    open: (__VLS_ctx.docModalVisible),
    title: "添加文档元数据",
    confirmLoading: (__VLS_ctx.submitting),
    destroyOnClose: true,
}));
const __VLS_150 = __VLS_149({
    ...{ 'onOk': {} },
    open: (__VLS_ctx.docModalVisible),
    title: "添加文档元数据",
    confirmLoading: (__VLS_ctx.submitting),
    destroyOnClose: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_149));
let __VLS_152;
let __VLS_153;
let __VLS_154;
const __VLS_155 = {
    onOk: (__VLS_ctx.submitDoc)
};
__VLS_151.slots.default;
const __VLS_156 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
    layout: "vertical",
}));
const __VLS_158 = __VLS_157({
    layout: "vertical",
}, ...__VLS_functionalComponentArgsRest(__VLS_157));
__VLS_159.slots.default;
const __VLS_160 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
    label: "所属知识库 ID",
    required: true,
}));
const __VLS_162 = __VLS_161({
    label: "所属知识库 ID",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_161));
__VLS_163.slots.default;
const __VLS_164 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
    value: (__VLS_ctx.docForm.knowledge_base_id),
    placeholder: "知识库 UUID",
}));
const __VLS_166 = __VLS_165({
    value: (__VLS_ctx.docForm.knowledge_base_id),
    placeholder: "知识库 UUID",
}, ...__VLS_functionalComponentArgsRest(__VLS_165));
var __VLS_163;
const __VLS_168 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
    label: "所属组织",
    required: true,
}));
const __VLS_170 = __VLS_169({
    label: "所属组织",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_169));
__VLS_171.slots.default;
const __VLS_172 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
    value: (__VLS_ctx.docForm.owner_org_unit_id),
    placeholder: "选择所属组织",
    showSearch: true,
    filterOption: (__VLS_ctx.filterOrgOption),
    options: (__VLS_ctx.orgOptions),
    ...{ class: "modal-select" },
    ...{ style: {} },
}));
const __VLS_174 = __VLS_173({
    value: (__VLS_ctx.docForm.owner_org_unit_id),
    placeholder: "选择所属组织",
    showSearch: true,
    filterOption: (__VLS_ctx.filterOrgOption),
    options: (__VLS_ctx.orgOptions),
    ...{ class: "modal-select" },
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_173));
var __VLS_171;
const __VLS_176 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
    label: "文件名",
    required: true,
}));
const __VLS_178 = __VLS_177({
    label: "文件名",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_177));
__VLS_179.slots.default;
const __VLS_180 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
    value: (__VLS_ctx.docForm.file_name),
    placeholder: "如 contract-sample.pdf",
}));
const __VLS_182 = __VLS_181({
    value: (__VLS_ctx.docForm.file_name),
    placeholder: "如 contract-sample.pdf",
}, ...__VLS_functionalComponentArgsRest(__VLS_181));
var __VLS_179;
const __VLS_184 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({
    label: "Provider Doc ID",
}));
const __VLS_186 = __VLS_185({
    label: "Provider Doc ID",
}, ...__VLS_functionalComponentArgsRest(__VLS_185));
__VLS_187.slots.default;
const __VLS_188 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
    value: (__VLS_ctx.docForm.provider_doc_id),
    placeholder: "Dify 文档 ID",
}));
const __VLS_190 = __VLS_189({
    value: (__VLS_ctx.docForm.provider_doc_id),
    placeholder: "Dify 文档 ID",
}, ...__VLS_functionalComponentArgsRest(__VLS_189));
var __VLS_187;
const __VLS_192 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({
    label: "Storage URI",
}));
const __VLS_194 = __VLS_193({
    label: "Storage URI",
}, ...__VLS_functionalComponentArgsRest(__VLS_193));
__VLS_195.slots.default;
const __VLS_196 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
    value: (__VLS_ctx.docForm.storage_uri),
    placeholder: "文件存储路径",
}));
const __VLS_198 = __VLS_197({
    value: (__VLS_ctx.docForm.storage_uri),
    placeholder: "文件存储路径",
}, ...__VLS_functionalComponentArgsRest(__VLS_197));
var __VLS_195;
var __VLS_159;
var __VLS_151;
/** @type {__VLS_StyleScopedClasses['page-block']} */ ;
/** @type {__VLS_StyleScopedClasses['page-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['page-subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['primary-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['secondary-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-select']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-select']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-select']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            FileAddOutlined: FileAddOutlined,
            PlusOutlined: PlusOutlined,
            formatDateTime: formatDateTime,
            kbLoading: kbLoading,
            kbError: kbError,
            kbs: kbs,
            kbModalVisible: kbModalVisible,
            kbForm: kbForm,
            providerOptions: providerOptions,
            kbPagination: kbPagination,
            docPagination: docPagination,
            onKbTableChange: onKbTableChange,
            onDocTableChange: onDocTableChange,
            orgOptions: orgOptions,
            kbColumns: kbColumns,
            docLoading: docLoading,
            docError: docError,
            docs: docs,
            docModalVisible: docModalVisible,
            docForm: docForm,
            docColumns: docColumns,
            activeTab: activeTab,
            submitting: submitting,
            parseColor: parseColor,
            loadKBs: loadKBs,
            loadDocs: loadDocs,
            filterOrgOption: filterOrgOption,
            openCreateKB: openCreateKB,
            submitKB: submitKB,
            openCreateDoc: openCreateDoc,
            submitDoc: submitDoc,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
