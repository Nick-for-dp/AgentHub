import { onMounted, reactive, ref } from 'vue';
import { fetchAgentBusinessFollowups, fetchDailyActiveUsers, fetchUserChatDuration, fetchUserMessageCounts, } from '../../api/admin';
import { formatDateTime, toISOString } from '../../utils/format';
// ── 状态 ──
const loading = ref(false);
const error = ref(false);
const activeTab = ref('dau');
// 日活趋势
const dauData = ref([]);
// 消息排行
const msgData = reactive({ items: [], total: 0, page: 1, page_size: 10 });
// 活跃跨度
const durData = reactive({ items: [], total: 0, page: 1, page_size: 10 });
// 业务追问
const fwData = reactive({ items: [], total: 0, page: 1, page_size: 10 });
// 全局筛选
const filter = reactive({
    dateRange: undefined,
    agentCode: '',
    userId: '',
    orgUnitId: '',
});
let requestSeq = 0;
// ── 分页对象 ──
const msgPagination = makePagination(msgData, 'msg');
const durPagination = makePagination(durData, 'dur');
const fwPagination = makePagination(fwData, 'fw');
function makePagination(data, _label) {
    return reactive({
        current: data.page,
        pageSize: data.page_size,
        total: data.total,
        showSizeChanger: true,
        pageSizeOptions: ['10', '20', '50'],
        size: 'small',
        showTotal: (t) => `共 ${t} 条`,
    });
}
// ── 列定义 ──
const dauColumns = [
    { title: '日期', dataIndex: 'date', key: 'date', width: 160 },
    { title: '活跃用户数', dataIndex: 'active_users', key: 'active_users', width: 140 },
];
const msgColumns = [
    { title: '用户', key: 'user', ellipsis: true },
    { title: '组织', key: 'org', width: 150 },
    { title: '消息数', dataIndex: 'message_count', key: 'message_count', width: 100, sorter: false },
    { title: '关联 Agent', key: 'agents', width: 180 },
    { title: '最近发送时间', key: 'last_message_at', width: 170 },
];
const durColumns = [
    { title: '用户', key: 'user', width: 140 },
    { title: '日期', dataIndex: 'chat_date', key: 'chat_date', width: 120 },
    { title: '消息数', dataIndex: 'message_count', key: 'message_count', width: 90 },
    { title: '估算跨度', key: 'span', width: 130 },
    { title: '首条 / 末条时间', key: 'time_range', width: 340 },
];
const fwColumns = [
    { title: '智能体', key: 'agent', width: 200 },
    { title: '追问次数', dataIndex: 'followup_count', key: 'followup_count', width: 120 },
];
// ── 数据加载 ──
function buildFilterParams(overrides = {}) {
    return {
        created_from: toISOString(filter.dateRange?.[0]),
        created_to: toISOString(filter.dateRange?.[1]),
        agent_code: filter.agentCode || undefined,
        user_id: filter.userId || undefined,
        org_unit_id: filter.orgUnitId || undefined,
        page: overrides.page ?? 1,
        page_size: overrides.page_size ?? 10,
    };
}
function isLatestRequest(seq) {
    return seq == null || seq === requestSeq;
}
async function loadDAU(seq) {
    const params = buildFilterParams();
    const result = await fetchDailyActiveUsers(params);
    if (!isLatestRequest(seq))
        return;
    dauData.value = result;
}
async function loadMessages(p, seq) {
    const params = buildFilterParams({ page: msgData.page, page_size: msgData.page_size, ...p });
    const result = await fetchUserMessageCounts(params);
    if (!isLatestRequest(seq))
        return;
    msgData.items = result.items;
    msgData.total = result.total;
    msgData.page = result.page;
    msgData.page_size = result.page_size;
    syncPagination(msgPagination, msgData);
}
async function loadDuration(p, seq) {
    const params = buildFilterParams({ page: durData.page, page_size: durData.page_size, ...p });
    const result = await fetchUserChatDuration(params);
    if (!isLatestRequest(seq))
        return;
    durData.items = result.items;
    durData.total = result.total;
    durData.page = result.page;
    durData.page_size = result.page_size;
    syncPagination(durPagination, durData);
}
async function loadFollowups(p, seq) {
    const params = buildFilterParams({ page: fwData.page, page_size: fwData.page_size, ...p });
    const result = await fetchAgentBusinessFollowups(params);
    if (!isLatestRequest(seq))
        return;
    fwData.items = result.items;
    fwData.total = result.total;
    fwData.page = result.page;
    fwData.page_size = result.page_size;
    syncPagination(fwPagination, fwData);
}
function syncPagination(pag, data) {
    pag.current = data.page;
    pag.pageSize = data.page_size;
    pag.total = data.total;
}
async function loadActiveTab() {
    const seq = ++requestSeq;
    loading.value = true;
    error.value = false;
    try {
        switch (activeTab.value) {
            case 'dau':
                await loadDAU(seq);
                break;
            case 'messages':
                await loadMessages(undefined, seq);
                break;
            case 'duration':
                await loadDuration(undefined, seq);
                break;
            case 'followups':
                await loadFollowups(undefined, seq);
                break;
        }
    }
    catch {
        if (seq === requestSeq) {
            error.value = true;
        }
    }
    finally {
        if (seq === requestSeq) {
            loading.value = false;
        }
    }
}
// ── 交互 ──
function search() {
    // 重置各 Tab 分页
    msgData.page = 1;
    durData.page = 1;
    fwData.page = 1;
    loadActiveTab();
}
function resetFilter() {
    filter.dateRange = undefined;
    filter.agentCode = '';
    filter.userId = '';
    filter.orgUnitId = '';
    search();
}
function onTabChange() {
    loadActiveTab();
}
function onMsgTableChange(p) {
    const changed = p.pageSize !== msgData.page_size;
    if (changed)
        msgData.page = 1;
    else
        msgData.page = p.current;
    msgData.page_size = p.pageSize;
    loadMessages();
}
function onDurTableChange(p) {
    const changed = p.pageSize !== durData.page_size;
    if (changed)
        durData.page = 1;
    else
        durData.page = p.current;
    durData.page_size = p.pageSize;
    loadDuration();
}
function onFwTableChange(p) {
    const changed = p.pageSize !== fwData.page_size;
    if (changed)
        fwData.page = 1;
    else
        fwData.page = p.current;
    fwData.page_size = p.pageSize;
    loadFollowups();
}
// ── 格式化 ──
function formatDuration(seconds) {
    if (seconds < 60)
        return `${seconds} 秒`;
    if (seconds < 3600)
        return `${Math.round(seconds / 60)} 分钟`;
    return `${Math.round(seconds / 3600 * 10) / 10} 小时`;
}
function durationRowKey(record) {
    return `${record.user_id}-${record.chat_date}`;
}
// ── 初始化 ──
onMounted(loadActiveTab);
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['page-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-form']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-form']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-form']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-form']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-form']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-picker']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-form']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-form']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-actions']} */ ;
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
if (__VLS_ctx.error) {
    const __VLS_0 = {}.AResult;
    /** @type {[typeof __VLS_components.AResult, typeof __VLS_components.aResult, typeof __VLS_components.AResult, typeof __VLS_components.aResult, ]} */ ;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
        status: "error",
        title: "加载失败",
        subTitle: "无法获取统计数据",
    }));
    const __VLS_2 = __VLS_1({
        status: "error",
        title: "加载失败",
        subTitle: "无法获取统计数据",
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    __VLS_3.slots.default;
    {
        const { extra: __VLS_thisSlot } = __VLS_3.slots;
        const __VLS_4 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
            ...{ 'onClick': {} },
            type: "primary",
        }));
        const __VLS_6 = __VLS_5({
            ...{ 'onClick': {} },
            type: "primary",
        }, ...__VLS_functionalComponentArgsRest(__VLS_5));
        let __VLS_8;
        let __VLS_9;
        let __VLS_10;
        const __VLS_11 = {
            onClick: (__VLS_ctx.loadActiveTab)
        };
        __VLS_7.slots.default;
        var __VLS_7;
    }
    var __VLS_3;
}
else {
    const __VLS_12 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
        size: "small",
        ...{ class: "filter-card" },
        ...{ style: {} },
    }));
    const __VLS_14 = __VLS_13({
        size: "small",
        ...{ class: "filter-card" },
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_13));
    __VLS_15.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.form, __VLS_intrinsicElements.form)({
        ...{ onSubmit: (__VLS_ctx.search) },
        ...{ class: "filter-form" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "filter-field filter-date" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "filter-label" },
    });
    const __VLS_16 = {}.ARangePicker;
    /** @type {[typeof __VLS_components.ARangePicker, typeof __VLS_components.aRangePicker, ]} */ ;
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
        value: (__VLS_ctx.filter.dateRange),
        showTime: true,
        format: "YYYY-MM-DD HH:mm:ss",
        placeholder: (['开始时间', '结束时间']),
        allowClear: true,
        size: "small",
    }));
    const __VLS_18 = __VLS_17({
        value: (__VLS_ctx.filter.dateRange),
        showTime: true,
        format: "YYYY-MM-DD HH:mm:ss",
        placeholder: (['开始时间', '结束时间']),
        allowClear: true,
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_17));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "filter-field filter-agent" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "filter-label" },
    });
    const __VLS_20 = {}.AInput;
    /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
        value: (__VLS_ctx.filter.agentCode),
        placeholder: "agent code",
        allowClear: true,
        size: "small",
    }));
    const __VLS_22 = __VLS_21({
        value: (__VLS_ctx.filter.agentCode),
        placeholder: "agent code",
        allowClear: true,
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "filter-field filter-user" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "filter-label" },
    });
    const __VLS_24 = {}.AInput;
    /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
        value: (__VLS_ctx.filter.userId),
        placeholder: "user id",
        allowClear: true,
        size: "small",
    }));
    const __VLS_26 = __VLS_25({
        value: (__VLS_ctx.filter.userId),
        placeholder: "user id",
        allowClear: true,
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "filter-field filter-org" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "filter-label" },
    });
    const __VLS_28 = {}.AInput;
    /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
        value: (__VLS_ctx.filter.orgUnitId),
        placeholder: "org unit id",
        allowClear: true,
        size: "small",
    }));
    const __VLS_30 = __VLS_29({
        value: (__VLS_ctx.filter.orgUnitId),
        placeholder: "org unit id",
        allowClear: true,
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_29));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "filter-actions" },
    });
    const __VLS_32 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
        type: "primary",
        htmlType: "submit",
        size: "small",
    }));
    const __VLS_34 = __VLS_33({
        type: "primary",
        htmlType: "submit",
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_33));
    __VLS_35.slots.default;
    var __VLS_35;
    const __VLS_36 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
        ...{ 'onClick': {} },
        size: "small",
    }));
    const __VLS_38 = __VLS_37({
        ...{ 'onClick': {} },
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_37));
    let __VLS_40;
    let __VLS_41;
    let __VLS_42;
    const __VLS_43 = {
        onClick: (__VLS_ctx.resetFilter)
    };
    __VLS_39.slots.default;
    var __VLS_39;
    var __VLS_15;
    const __VLS_44 = {}.ATabs;
    /** @type {[typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, ]} */ ;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
        ...{ 'onChange': {} },
        activeKey: (__VLS_ctx.activeTab),
    }));
    const __VLS_46 = __VLS_45({
        ...{ 'onChange': {} },
        activeKey: (__VLS_ctx.activeTab),
    }, ...__VLS_functionalComponentArgsRest(__VLS_45));
    let __VLS_48;
    let __VLS_49;
    let __VLS_50;
    const __VLS_51 = {
        onChange: (__VLS_ctx.onTabChange)
    };
    __VLS_47.slots.default;
    const __VLS_52 = {}.ATabPane;
    /** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
        key: "dau",
        tab: "日活趋势",
    }));
    const __VLS_54 = __VLS_53({
        key: "dau",
        tab: "日活趋势",
    }, ...__VLS_functionalComponentArgsRest(__VLS_53));
    const __VLS_56 = {}.ATabPane;
    /** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
        key: "messages",
        tab: "消息排行",
    }));
    const __VLS_58 = __VLS_57({
        key: "messages",
        tab: "消息排行",
    }, ...__VLS_functionalComponentArgsRest(__VLS_57));
    const __VLS_60 = {}.ATabPane;
    /** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
        key: "duration",
        tab: "活跃跨度",
    }));
    const __VLS_62 = __VLS_61({
        key: "duration",
        tab: "活跃跨度",
    }, ...__VLS_functionalComponentArgsRest(__VLS_61));
    const __VLS_64 = {}.ATabPane;
    /** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
        key: "followups",
        tab: "业务追问",
    }));
    const __VLS_66 = __VLS_65({
        key: "followups",
        tab: "业务追问",
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    var __VLS_47;
    if (__VLS_ctx.activeTab === 'dau') {
        const __VLS_68 = {}.ATable;
        /** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
        // @ts-ignore
        const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
            columns: (__VLS_ctx.dauColumns),
            dataSource: (__VLS_ctx.dauData),
            loading: (__VLS_ctx.loading),
            pagination: (false),
            rowKey: "date",
            size: "middle",
            ...{ style: {} },
        }));
        const __VLS_70 = __VLS_69({
            columns: (__VLS_ctx.dauColumns),
            dataSource: (__VLS_ctx.dauData),
            loading: (__VLS_ctx.loading),
            pagination: (false),
            rowKey: "date",
            size: "middle",
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_69));
    }
    if (__VLS_ctx.activeTab === 'messages') {
        const __VLS_72 = {}.ATable;
        /** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
        // @ts-ignore
        const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
            ...{ 'onChange': {} },
            columns: (__VLS_ctx.msgColumns),
            dataSource: (__VLS_ctx.msgData.items),
            loading: (__VLS_ctx.loading),
            pagination: (__VLS_ctx.msgPagination),
            rowKey: "user_id",
            size: "middle",
            ...{ style: {} },
        }));
        const __VLS_74 = __VLS_73({
            ...{ 'onChange': {} },
            columns: (__VLS_ctx.msgColumns),
            dataSource: (__VLS_ctx.msgData.items),
            loading: (__VLS_ctx.loading),
            pagination: (__VLS_ctx.msgPagination),
            rowKey: "user_id",
            size: "middle",
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_73));
        let __VLS_76;
        let __VLS_77;
        let __VLS_78;
        const __VLS_79 = {
            onChange: (__VLS_ctx.onMsgTableChange)
        };
        __VLS_75.slots.default;
        {
            const { bodyCell: __VLS_thisSlot } = __VLS_75.slots;
            const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
            if (column.key === 'user') {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "primary-cell" },
                });
                (record.user_name || '-');
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "secondary-cell" },
                });
                (record.phone_normalized || '未留电话');
            }
            if (column.key === 'org') {
                (record.org_unit_name || '-');
            }
            if (column.key === 'agents') {
                for (const [code] of __VLS_getVForSourceType((record.agent_codes))) {
                    const __VLS_80 = {}.ATag;
                    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                    // @ts-ignore
                    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
                        key: (code),
                        color: "blue",
                        size: "small",
                    }));
                    const __VLS_82 = __VLS_81({
                        key: (code),
                        color: "blue",
                        size: "small",
                    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
                    __VLS_83.slots.default;
                    (code);
                    var __VLS_83;
                }
                if (!record.agent_codes.length) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                }
            }
            if (column.key === 'last_message_at') {
                (__VLS_ctx.formatDateTime(record.last_message_at));
            }
        }
        var __VLS_75;
    }
    if (__VLS_ctx.activeTab === 'duration') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        const __VLS_84 = {}.ATable;
        /** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
        // @ts-ignore
        const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
            ...{ 'onChange': {} },
            columns: (__VLS_ctx.durColumns),
            dataSource: (__VLS_ctx.durData.items),
            loading: (__VLS_ctx.loading),
            pagination: (__VLS_ctx.durPagination),
            rowKey: (__VLS_ctx.durationRowKey),
            size: "middle",
            ...{ style: {} },
        }));
        const __VLS_86 = __VLS_85({
            ...{ 'onChange': {} },
            columns: (__VLS_ctx.durColumns),
            dataSource: (__VLS_ctx.durData.items),
            loading: (__VLS_ctx.loading),
            pagination: (__VLS_ctx.durPagination),
            rowKey: (__VLS_ctx.durationRowKey),
            size: "middle",
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_85));
        let __VLS_88;
        let __VLS_89;
        let __VLS_90;
        const __VLS_91 = {
            onChange: (__VLS_ctx.onDurTableChange)
        };
        __VLS_87.slots.default;
        {
            const { bodyCell: __VLS_thisSlot } = __VLS_87.slots;
            const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
            if (column.key === 'user') {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "primary-cell" },
                });
                (record.user_name || '-');
            }
            if (column.key === 'span') {
                (__VLS_ctx.formatDuration(record.duration_seconds));
            }
            if (column.key === 'time_range') {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                (__VLS_ctx.formatDateTime(record.first_message_at));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                (__VLS_ctx.formatDateTime(record.last_message_at));
            }
        }
        var __VLS_87;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "metric-note" },
        });
    }
    if (__VLS_ctx.activeTab === 'followups') {
        const __VLS_92 = {}.ATable;
        /** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
        // @ts-ignore
        const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
            ...{ 'onChange': {} },
            columns: (__VLS_ctx.fwColumns),
            dataSource: (__VLS_ctx.fwData.items),
            loading: (__VLS_ctx.loading),
            pagination: (__VLS_ctx.fwPagination),
            rowKey: "agent_code",
            size: "middle",
            ...{ style: {} },
        }));
        const __VLS_94 = __VLS_93({
            ...{ 'onChange': {} },
            columns: (__VLS_ctx.fwColumns),
            dataSource: (__VLS_ctx.fwData.items),
            loading: (__VLS_ctx.loading),
            pagination: (__VLS_ctx.fwPagination),
            rowKey: "agent_code",
            size: "middle",
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_93));
        let __VLS_96;
        let __VLS_97;
        let __VLS_98;
        const __VLS_99 = {
            onChange: (__VLS_ctx.onFwTableChange)
        };
        __VLS_95.slots.default;
        {
            const { bodyCell: __VLS_thisSlot } = __VLS_95.slots;
            const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
            if (column.key === 'agent') {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "primary-cell" },
                });
                (record.agent_name || record.agent_code || '-');
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "secondary-cell" },
                });
                (record.agent_code || '-');
            }
        }
        var __VLS_95;
    }
}
/** @type {__VLS_StyleScopedClasses['page-block']} */ ;
/** @type {__VLS_StyleScopedClasses['page-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['page-subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-card']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-form']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-field']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-date']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-field']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-agent']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-field']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-user']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-field']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-org']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['primary-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['secondary-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['primary-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-note']} */ ;
/** @type {__VLS_StyleScopedClasses['primary-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['secondary-cell']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            formatDateTime: formatDateTime,
            loading: loading,
            error: error,
            activeTab: activeTab,
            dauData: dauData,
            msgData: msgData,
            durData: durData,
            fwData: fwData,
            filter: filter,
            msgPagination: msgPagination,
            durPagination: durPagination,
            fwPagination: fwPagination,
            dauColumns: dauColumns,
            msgColumns: msgColumns,
            durColumns: durColumns,
            fwColumns: fwColumns,
            loadActiveTab: loadActiveTab,
            search: search,
            resetFilter: resetFilter,
            onTabChange: onTabChange,
            onMsgTableChange: onMsgTableChange,
            onDurTableChange: onDurTableChange,
            onFwTableChange: onFwTableChange,
            formatDuration: formatDuration,
            durationRowKey: durationRowKey,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
