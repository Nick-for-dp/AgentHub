import { onMounted, reactive, ref } from 'vue';
import { listInvocationRecords } from '../../api/admin';
import { formatDateTime, toISOString } from '../../utils/format';
const loading = ref(false);
const error = ref(false);
const records = ref([]);
const total = ref(0);
const filter = reactive({
    agent_code: '',
    status: '',
    created_from: undefined,
    created_to: undefined,
    page: 1,
    page_size: 10,
});
const pagination = reactive({
    current: 1,
    pageSize: 10,
    total: 0,
    showSizeChanger: true,
    pageSizeOptions: ['10', '20', '50'],
    size: 'small',
    showTotal: (t) => `共 ${t} 条`,
});
const statusOptions = [
    { label: '全部', value: '' },
    { label: '成功', value: 'SUCCEEDED' },
    { label: '失败', value: 'FAILED' },
];
const columns = [
    { title: '客户', key: 'customer', width: 180 },
    { title: '智能体', key: 'agent', width: 180 },
    { title: '提问摘要', key: 'question', ellipsis: true },
    { title: '状态', key: 'status', width: 92 },
    { title: '耗时', key: 'latency_ms', width: 90 },
    { title: '调用时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
    { title: '操作', key: 'action', width: 70 },
];
// ---- 详情抽屉 ----
const detailVisible = ref(false);
const detail = ref(null);
function openDetail(record) {
    detail.value = record;
    detailVisible.value = true;
}
// ---- 查询 ----
async function load() {
    loading.value = true;
    error.value = false;
    try {
        const result = await listInvocationRecords({
            agent_code: filter.agent_code || undefined,
            status: filter.status || undefined,
            created_from: toISOString(filter.created_from),
            created_to: toISOString(filter.created_to),
            page: filter.page,
            page_size: filter.page_size,
        });
        records.value = result.items;
        total.value = result.total;
        pagination.current = result.page;
        pagination.pageSize = result.page_size;
        pagination.total = result.total;
    }
    catch {
        error.value = true;
    }
    finally {
        loading.value = false;
    }
}
function search() {
    detailVisible.value = false;
    detail.value = null;
    filter.page = 1;
    pagination.current = 1;
    load();
}
function resetFilter() {
    detailVisible.value = false;
    detail.value = null;
    filter.agent_code = '';
    filter.status = '';
    filter.created_from = undefined;
    filter.created_to = undefined;
    filter.page = 1;
    pagination.current = 1;
    load();
}
function handleStatusChange() {
    search();
}
function onTableChange(p) {
    detailVisible.value = false;
    detail.value = null;
    const pageSizeChanged = p.pageSize !== filter.page_size;
    filter.page = pageSizeChanged ? 1 : p.current;
    filter.page_size = p.pageSize;
    pagination.current = filter.page;
    pagination.pageSize = p.pageSize;
    load();
}
function invokeStatusColor(status) {
    const map = {
        SUCCEEDED: 'green',
        FAILED: 'red',
        STREAMING: 'blue',
        PENDING: 'default',
    };
    return map[status] ?? 'default';
}
function invokeStatusText(status) {
    const map = {
        SUCCEEDED: '成功',
        FAILED: '失败',
        STREAMING: '进行中',
        PENDING: '等待中',
    };
    return map[status] ?? status;
}
function questionSummary(record) {
    const value = record.input?.question;
    return typeof value === 'string' && value.trim() ? value : '-';
}
function formatLatency(value) {
    if (value == null)
        return '-';
    return value >= 1000 ? `${(value / 1000).toFixed(1)} s` : `${value} ms`;
}
onMounted(load);
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
/** @type {__VLS_StyleScopedClasses['filter-form']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-picker']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-form']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-form']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-form']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-form']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-form']} */ ;
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
        subTitle: "无法获取调用记录",
    }));
    const __VLS_2 = __VLS_1({
        status: "error",
        title: "加载失败",
        subTitle: "无法获取调用记录",
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
            onClick: (__VLS_ctx.load)
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
        ...{ class: "filter-field filter-agent" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "filter-label" },
    });
    const __VLS_16 = {}.AInput;
    /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
        value: (__VLS_ctx.filter.agent_code),
        placeholder: "输入智能体编码",
        allowClear: true,
        size: "small",
    }));
    const __VLS_18 = __VLS_17({
        value: (__VLS_ctx.filter.agent_code),
        placeholder: "输入智能体编码",
        allowClear: true,
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_17));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "filter-field filter-status" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "filter-label" },
    });
    const __VLS_20 = {}.ARadioGroup;
    /** @type {[typeof __VLS_components.ARadioGroup, typeof __VLS_components.aRadioGroup, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.filter.status),
        size: "small",
        optionType: "button",
        buttonStyle: "solid",
        options: (__VLS_ctx.statusOptions),
    }));
    const __VLS_22 = __VLS_21({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.filter.status),
        size: "small",
        optionType: "button",
        buttonStyle: "solid",
        options: (__VLS_ctx.statusOptions),
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    let __VLS_24;
    let __VLS_25;
    let __VLS_26;
    const __VLS_27 = {
        onChange: (__VLS_ctx.handleStatusChange)
    };
    var __VLS_23;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "filter-field filter-date" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "filter-label" },
    });
    const __VLS_28 = {}.ADatePicker;
    /** @type {[typeof __VLS_components.ADatePicker, typeof __VLS_components.aDatePicker, ]} */ ;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
        value: (__VLS_ctx.filter.created_from),
        showTime: true,
        format: "YYYY-MM-DD HH:mm:ss",
        placeholder: "开始时间",
        allowClear: true,
        size: "small",
    }));
    const __VLS_30 = __VLS_29({
        value: (__VLS_ctx.filter.created_from),
        showTime: true,
        format: "YYYY-MM-DD HH:mm:ss",
        placeholder: "开始时间",
        allowClear: true,
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_29));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "filter-field filter-date" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "filter-label" },
    });
    const __VLS_32 = {}.ADatePicker;
    /** @type {[typeof __VLS_components.ADatePicker, typeof __VLS_components.aDatePicker, ]} */ ;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
        value: (__VLS_ctx.filter.created_to),
        showTime: true,
        format: "YYYY-MM-DD HH:mm:ss",
        placeholder: "截止时间",
        allowClear: true,
        size: "small",
    }));
    const __VLS_34 = __VLS_33({
        value: (__VLS_ctx.filter.created_to),
        showTime: true,
        format: "YYYY-MM-DD HH:mm:ss",
        placeholder: "截止时间",
        allowClear: true,
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_33));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "filter-actions" },
    });
    const __VLS_36 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
        type: "primary",
        htmlType: "submit",
        size: "small",
    }));
    const __VLS_38 = __VLS_37({
        type: "primary",
        htmlType: "submit",
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_37));
    __VLS_39.slots.default;
    var __VLS_39;
    const __VLS_40 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
        ...{ 'onClick': {} },
        size: "small",
    }));
    const __VLS_42 = __VLS_41({
        ...{ 'onClick': {} },
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
    let __VLS_44;
    let __VLS_45;
    let __VLS_46;
    const __VLS_47 = {
        onClick: (__VLS_ctx.resetFilter)
    };
    __VLS_43.slots.default;
    var __VLS_43;
    var __VLS_15;
    const __VLS_48 = {}.ATable;
    /** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
        ...{ 'onChange': {} },
        columns: (__VLS_ctx.columns),
        dataSource: (__VLS_ctx.records),
        loading: (__VLS_ctx.loading),
        pagination: (__VLS_ctx.pagination),
        rowKey: "id",
        size: "middle",
        ...{ style: {} },
    }));
    const __VLS_50 = __VLS_49({
        ...{ 'onChange': {} },
        columns: (__VLS_ctx.columns),
        dataSource: (__VLS_ctx.records),
        loading: (__VLS_ctx.loading),
        pagination: (__VLS_ctx.pagination),
        rowKey: "id",
        size: "middle",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_49));
    let __VLS_52;
    let __VLS_53;
    let __VLS_54;
    const __VLS_55 = {
        onChange: (__VLS_ctx.onTableChange)
    };
    __VLS_51.slots.default;
    {
        const { bodyCell: __VLS_thisSlot } = __VLS_51.slots;
        const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
        if (column.key === 'status') {
            const __VLS_56 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
                color: (__VLS_ctx.invokeStatusColor(record.status)),
            }));
            const __VLS_58 = __VLS_57({
                color: (__VLS_ctx.invokeStatusColor(record.status)),
            }, ...__VLS_functionalComponentArgsRest(__VLS_57));
            __VLS_59.slots.default;
            (__VLS_ctx.invokeStatusText(record.status));
            var __VLS_59;
        }
        if (column.key === 'customer') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "primary-cell" },
            });
            (record.customer_phone || '-');
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "secondary-cell" },
            });
            (record.customer_name || record.org_unit_name || '-');
        }
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
        if (column.key === 'question') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "question-text" },
            });
            (__VLS_ctx.questionSummary(record));
        }
        if (column.key === 'latency_ms') {
            (__VLS_ctx.formatLatency(record.latency_ms));
        }
        if (column.key === 'created_at') {
            (__VLS_ctx.formatDateTime(record.created_at));
        }
        if (column.key === 'action') {
            const __VLS_60 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }));
            const __VLS_62 = __VLS_61({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_61));
            let __VLS_64;
            let __VLS_65;
            let __VLS_66;
            const __VLS_67 = {
                onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.error))
                        return;
                    if (!(column.key === 'action'))
                        return;
                    __VLS_ctx.openDetail(record);
                }
            };
            __VLS_63.slots.default;
            var __VLS_63;
        }
    }
    var __VLS_51;
    const __VLS_68 = {}.ADrawer;
    /** @type {[typeof __VLS_components.ADrawer, typeof __VLS_components.aDrawer, typeof __VLS_components.ADrawer, typeof __VLS_components.aDrawer, ]} */ ;
    // @ts-ignore
    const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
        ...{ 'onClose': {} },
        title: "调用详情",
        open: (__VLS_ctx.detailVisible),
        width: (560),
    }));
    const __VLS_70 = __VLS_69({
        ...{ 'onClose': {} },
        title: "调用详情",
        open: (__VLS_ctx.detailVisible),
        width: (560),
    }, ...__VLS_functionalComponentArgsRest(__VLS_69));
    let __VLS_72;
    let __VLS_73;
    let __VLS_74;
    const __VLS_75 = {
        onClose: (...[$event]) => {
            if (!!(__VLS_ctx.error))
                return;
            __VLS_ctx.detailVisible = false;
        }
    };
    __VLS_71.slots.default;
    if (__VLS_ctx.detail) {
        const __VLS_76 = {}.ADescriptions;
        /** @type {[typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, ]} */ ;
        // @ts-ignore
        const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
            column: (1),
            size: "small",
            bordered: true,
        }));
        const __VLS_78 = __VLS_77({
            column: (1),
            size: "small",
            bordered: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_77));
        __VLS_79.slots.default;
        const __VLS_80 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
            label: "客户电话",
        }));
        const __VLS_82 = __VLS_81({
            label: "客户电话",
        }, ...__VLS_functionalComponentArgsRest(__VLS_81));
        __VLS_83.slots.default;
        (__VLS_ctx.detail.customer_phone ?? '-');
        var __VLS_83;
        const __VLS_84 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
            label: "客户名称",
        }));
        const __VLS_86 = __VLS_85({
            label: "客户名称",
        }, ...__VLS_functionalComponentArgsRest(__VLS_85));
        __VLS_87.slots.default;
        (__VLS_ctx.detail.customer_name ?? '-');
        var __VLS_87;
        const __VLS_88 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
            label: "客户组织",
        }));
        const __VLS_90 = __VLS_89({
            label: "客户组织",
        }, ...__VLS_functionalComponentArgsRest(__VLS_89));
        __VLS_91.slots.default;
        (__VLS_ctx.detail.org_unit_name ?? '-');
        var __VLS_91;
        const __VLS_92 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
            label: "Agent",
        }));
        const __VLS_94 = __VLS_93({
            label: "Agent",
        }, ...__VLS_functionalComponentArgsRest(__VLS_93));
        __VLS_95.slots.default;
        (__VLS_ctx.detail.agent_name ?? __VLS_ctx.detail.agent_code ?? __VLS_ctx.detail.agent_id);
        var __VLS_95;
        const __VLS_96 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
            label: "Agent Code",
        }));
        const __VLS_98 = __VLS_97({
            label: "Agent Code",
        }, ...__VLS_functionalComponentArgsRest(__VLS_97));
        __VLS_99.slots.default;
        (__VLS_ctx.detail.agent_code ?? '-');
        var __VLS_99;
        const __VLS_100 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
            label: "Request ID",
        }));
        const __VLS_102 = __VLS_101({
            label: "Request ID",
        }, ...__VLS_functionalComponentArgsRest(__VLS_101));
        __VLS_103.slots.default;
        (__VLS_ctx.detail.request_id);
        var __VLS_103;
        const __VLS_104 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
            label: "状态",
        }));
        const __VLS_106 = __VLS_105({
            label: "状态",
        }, ...__VLS_functionalComponentArgsRest(__VLS_105));
        __VLS_107.slots.default;
        const __VLS_108 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
            color: (__VLS_ctx.invokeStatusColor(__VLS_ctx.detail.status)),
        }));
        const __VLS_110 = __VLS_109({
            color: (__VLS_ctx.invokeStatusColor(__VLS_ctx.detail.status)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_109));
        __VLS_111.slots.default;
        (__VLS_ctx.detail.status);
        var __VLS_111;
        var __VLS_107;
        const __VLS_112 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
            label: "调用方式",
        }));
        const __VLS_114 = __VLS_113({
            label: "调用方式",
        }, ...__VLS_functionalComponentArgsRest(__VLS_113));
        __VLS_115.slots.default;
        (__VLS_ctx.detail.caller_type === 'USER' ? '网页登录' : 'API Key');
        var __VLS_115;
        if (__VLS_ctx.detail.api_key_id) {
            const __VLS_116 = {}.ADescriptionsItem;
            /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
            // @ts-ignore
            const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
                label: "API Key",
            }));
            const __VLS_118 = __VLS_117({
                label: "API Key",
            }, ...__VLS_functionalComponentArgsRest(__VLS_117));
            __VLS_119.slots.default;
            (__VLS_ctx.detail.api_key_name ?? __VLS_ctx.detail.api_key_prefix ?? __VLS_ctx.detail.api_key_id);
            var __VLS_119;
        }
        const __VLS_120 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
            label: "渠道",
        }));
        const __VLS_122 = __VLS_121({
            label: "渠道",
        }, ...__VLS_functionalComponentArgsRest(__VLS_121));
        __VLS_123.slots.default;
        (__VLS_ctx.detail.source_channel ?? '-');
        var __VLS_123;
        const __VLS_124 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
            label: "耗时",
        }));
        const __VLS_126 = __VLS_125({
            label: "耗时",
        }, ...__VLS_functionalComponentArgsRest(__VLS_125));
        __VLS_127.slots.default;
        (__VLS_ctx.formatLatency(__VLS_ctx.detail.latency_ms));
        var __VLS_127;
        const __VLS_128 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
            label: "错误码",
        }));
        const __VLS_130 = __VLS_129({
            label: "错误码",
        }, ...__VLS_functionalComponentArgsRest(__VLS_129));
        __VLS_131.slots.default;
        (__VLS_ctx.detail.error_code ?? '-');
        var __VLS_131;
        const __VLS_132 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
            label: "错误信息",
        }));
        const __VLS_134 = __VLS_133({
            label: "错误信息",
        }, ...__VLS_functionalComponentArgsRest(__VLS_133));
        __VLS_135.slots.default;
        (__VLS_ctx.detail.error_message ?? '-');
        var __VLS_135;
        const __VLS_136 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
            label: "创建时间",
        }));
        const __VLS_138 = __VLS_137({
            label: "创建时间",
        }, ...__VLS_functionalComponentArgsRest(__VLS_137));
        __VLS_139.slots.default;
        (__VLS_ctx.formatDateTime(__VLS_ctx.detail.created_at));
        var __VLS_139;
        const __VLS_140 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
            label: "完成时间",
        }));
        const __VLS_142 = __VLS_141({
            label: "完成时间",
        }, ...__VLS_functionalComponentArgsRest(__VLS_141));
        __VLS_143.slots.default;
        (__VLS_ctx.formatDateTime(__VLS_ctx.detail.finished_at));
        var __VLS_143;
        var __VLS_79;
        const __VLS_144 = {}.ADivider;
        /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
        // @ts-ignore
        const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({}));
        const __VLS_146 = __VLS_145({}, ...__VLS_functionalComponentArgsRest(__VLS_145));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
            ...{ class: "json-block" },
        });
        (JSON.stringify(__VLS_ctx.detail.input, null, 2));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
            ...{ class: "json-block" },
        });
        (JSON.stringify(__VLS_ctx.detail.output, null, 2));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
            ...{ class: "json-block" },
        });
        (JSON.stringify(__VLS_ctx.detail.runtime_snapshot, null, 2));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
            ...{ class: "json-block" },
        });
        (JSON.stringify(__VLS_ctx.detail.token_usage, null, 2));
    }
    var __VLS_71;
}
/** @type {__VLS_StyleScopedClasses['page-block']} */ ;
/** @type {__VLS_StyleScopedClasses['page-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['page-subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-card']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-form']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-field']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-agent']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-field']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-status']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-field']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-date']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-field']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-date']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['primary-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['secondary-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['primary-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['secondary-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['question-text']} */ ;
/** @type {__VLS_StyleScopedClasses['json-block']} */ ;
/** @type {__VLS_StyleScopedClasses['json-block']} */ ;
/** @type {__VLS_StyleScopedClasses['json-block']} */ ;
/** @type {__VLS_StyleScopedClasses['json-block']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            formatDateTime: formatDateTime,
            loading: loading,
            error: error,
            records: records,
            filter: filter,
            pagination: pagination,
            statusOptions: statusOptions,
            columns: columns,
            detailVisible: detailVisible,
            detail: detail,
            openDetail: openDetail,
            load: load,
            search: search,
            resetFilter: resetFilter,
            handleStatusChange: handleStatusChange,
            onTableChange: onTableChange,
            invokeStatusColor: invokeStatusColor,
            invokeStatusText: invokeStatusText,
            questionSummary: questionSummary,
            formatLatency: formatLatency,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
