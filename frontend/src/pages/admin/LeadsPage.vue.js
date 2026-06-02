import { onMounted, reactive, ref } from 'vue';
import { listSalesLeads } from '../../api/admin';
import { formatDateTime, toISOString } from '../../utils/format';
const loading = ref(false);
const error = ref(false);
const leads = ref([]);
const filter = reactive({
    keyword: '',
    agent_code: '',
    region: '',
    status: '',
    has_contact: undefined,
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
    { label: '待补充', value: 'PROVISIONAL' },
    { label: '已识别', value: 'IDENTIFIED' },
    { label: '已完整', value: 'QUALIFIED' },
    { label: '已关闭', value: 'CLOSED' },
    { label: '已丢弃', value: 'DISCARDED' },
];
const contactOptions = [
    { label: '全部', value: undefined },
    { label: '已有联系方式', value: true },
    { label: '缺联系方式', value: false },
];
const columns = [
    { title: '需求', key: 'requirement', ellipsis: true },
    { title: '客户', key: 'customer', width: 190 },
    { title: '地域', key: 'region', width: 100 },
    { title: '智能体', key: 'agent', width: 160 },
    { title: '状态', key: 'status', width: 92 },
    { title: '待补充', key: 'missing_fields', width: 150 },
    { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 170 },
    { title: '操作', key: 'action', width: 70 },
];
const detailVisible = ref(false);
const detail = ref(null);
function openDetail(record) {
    detail.value = record;
    detailVisible.value = true;
}
async function load() {
    loading.value = true;
    error.value = false;
    try {
        const result = await listSalesLeads({
            keyword: filter.keyword || undefined,
            agent_code: filter.agent_code || undefined,
            region: filter.region || undefined,
            status: filter.status || undefined,
            has_contact: filter.has_contact,
            created_from: toISOString(filter.created_from),
            created_to: toISOString(filter.created_to),
            page: filter.page,
            page_size: filter.page_size,
        });
        leads.value = result.items;
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
    filter.keyword = '';
    filter.agent_code = '';
    filter.region = '';
    filter.status = '';
    filter.has_contact = undefined;
    filter.created_from = undefined;
    filter.created_to = undefined;
    filter.page = 1;
    pagination.current = 1;
    load();
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
function leadStatusColor(status) {
    const map = {
        PROVISIONAL: 'orange',
        IDENTIFIED: 'blue',
        QUALIFIED: 'green',
        CLOSED: 'default',
        DISCARDED: 'red',
    };
    return map[status] ?? 'default';
}
function leadStatusText(status) {
    const map = {
        PROVISIONAL: '待补充',
        IDENTIFIED: '已识别',
        QUALIFIED: '已完整',
        CLOSED: '已关闭',
        DISCARDED: '已丢弃',
    };
    return map[status] ?? status;
}
function missingFieldText(field) {
    const map = {
        requirement: '需求',
        region: '地域',
        contact: '联系方式',
    };
    return map[field] ?? field;
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
/** @type {__VLS_StyleScopedClasses['ant-picker']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-form']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-form']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
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
        subTitle: "无法获取线索记录",
    }));
    const __VLS_2 = __VLS_1({
        status: "error",
        title: "加载失败",
        subTitle: "无法获取线索记录",
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
        ...{ class: "filter-field filter-keyword" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "filter-label" },
    });
    const __VLS_16 = {}.AInput;
    /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
        value: (__VLS_ctx.filter.keyword),
        placeholder: "需求、地区、公司、电话",
        allowClear: true,
        size: "small",
    }));
    const __VLS_18 = __VLS_17({
        value: (__VLS_ctx.filter.keyword),
        placeholder: "需求、地区、公司、电话",
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
        value: (__VLS_ctx.filter.agent_code),
        placeholder: "Agent code",
        allowClear: true,
        size: "small",
    }));
    const __VLS_22 = __VLS_21({
        value: (__VLS_ctx.filter.agent_code),
        placeholder: "Agent code",
        allowClear: true,
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "filter-field filter-region" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "filter-label" },
    });
    const __VLS_24 = {}.AInput;
    /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
        value: (__VLS_ctx.filter.region),
        placeholder: "如 上海、广州",
        allowClear: true,
        size: "small",
    }));
    const __VLS_26 = __VLS_25({
        value: (__VLS_ctx.filter.region),
        placeholder: "如 上海、广州",
        allowClear: true,
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "filter-field filter-status" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "filter-label" },
    });
    const __VLS_28 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.filter.status),
        options: (__VLS_ctx.statusOptions),
        size: "small",
        ...{ style: {} },
    }));
    const __VLS_30 = __VLS_29({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.filter.status),
        options: (__VLS_ctx.statusOptions),
        size: "small",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_29));
    let __VLS_32;
    let __VLS_33;
    let __VLS_34;
    const __VLS_35 = {
        onChange: (__VLS_ctx.search)
    };
    var __VLS_31;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "filter-field filter-contact" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "filter-label" },
    });
    const __VLS_36 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.filter.has_contact),
        options: (__VLS_ctx.contactOptions),
        size: "small",
        ...{ style: {} },
    }));
    const __VLS_38 = __VLS_37({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.filter.has_contact),
        options: (__VLS_ctx.contactOptions),
        size: "small",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_37));
    let __VLS_40;
    let __VLS_41;
    let __VLS_42;
    const __VLS_43 = {
        onChange: (__VLS_ctx.search)
    };
    var __VLS_39;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "filter-field filter-date" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "filter-label" },
    });
    const __VLS_44 = {}.ADatePicker;
    /** @type {[typeof __VLS_components.ADatePicker, typeof __VLS_components.aDatePicker, ]} */ ;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
        value: (__VLS_ctx.filter.created_from),
        showTime: true,
        format: "YYYY-MM-DD HH:mm:ss",
        placeholder: "开始时间",
        allowClear: true,
        size: "small",
    }));
    const __VLS_46 = __VLS_45({
        value: (__VLS_ctx.filter.created_from),
        showTime: true,
        format: "YYYY-MM-DD HH:mm:ss",
        placeholder: "开始时间",
        allowClear: true,
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_45));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "filter-field filter-date" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "filter-label" },
    });
    const __VLS_48 = {}.ADatePicker;
    /** @type {[typeof __VLS_components.ADatePicker, typeof __VLS_components.aDatePicker, ]} */ ;
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
        value: (__VLS_ctx.filter.created_to),
        showTime: true,
        format: "YYYY-MM-DD HH:mm:ss",
        placeholder: "截止时间",
        allowClear: true,
        size: "small",
    }));
    const __VLS_50 = __VLS_49({
        value: (__VLS_ctx.filter.created_to),
        showTime: true,
        format: "YYYY-MM-DD HH:mm:ss",
        placeholder: "截止时间",
        allowClear: true,
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_49));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "filter-actions" },
    });
    const __VLS_52 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
        type: "primary",
        htmlType: "submit",
        size: "small",
    }));
    const __VLS_54 = __VLS_53({
        type: "primary",
        htmlType: "submit",
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_53));
    __VLS_55.slots.default;
    var __VLS_55;
    const __VLS_56 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
        ...{ 'onClick': {} },
        size: "small",
    }));
    const __VLS_58 = __VLS_57({
        ...{ 'onClick': {} },
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_57));
    let __VLS_60;
    let __VLS_61;
    let __VLS_62;
    const __VLS_63 = {
        onClick: (__VLS_ctx.resetFilter)
    };
    __VLS_59.slots.default;
    var __VLS_59;
    var __VLS_15;
    const __VLS_64 = {}.ATable;
    /** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
        ...{ 'onChange': {} },
        columns: (__VLS_ctx.columns),
        dataSource: (__VLS_ctx.leads),
        loading: (__VLS_ctx.loading),
        pagination: (__VLS_ctx.pagination),
        rowKey: "id",
        size: "middle",
        ...{ style: {} },
    }));
    const __VLS_66 = __VLS_65({
        ...{ 'onChange': {} },
        columns: (__VLS_ctx.columns),
        dataSource: (__VLS_ctx.leads),
        loading: (__VLS_ctx.loading),
        pagination: (__VLS_ctx.pagination),
        rowKey: "id",
        size: "middle",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    let __VLS_68;
    let __VLS_69;
    let __VLS_70;
    const __VLS_71 = {
        onChange: (__VLS_ctx.onTableChange)
    };
    __VLS_67.slots.default;
    {
        const { bodyCell: __VLS_thisSlot } = __VLS_67.slots;
        const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
        if (column.key === 'requirement') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "primary-cell" },
            });
            (record.requirement_summary || '-');
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "tag-line" },
            });
            for (const [type] of __VLS_getVForSourceType((record.requirement_types))) {
                const __VLS_72 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
                    key: (type),
                    color: "blue",
                }));
                const __VLS_74 = __VLS_73({
                    key: (type),
                    color: "blue",
                }, ...__VLS_functionalComponentArgsRest(__VLS_73));
                __VLS_75.slots.default;
                (type);
                var __VLS_75;
            }
            if (!record.requirement_types.length) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "secondary-cell" },
                });
            }
        }
        if (column.key === 'customer') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "primary-cell" },
            });
            (record.company_name || record.customer_name || '-');
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "secondary-cell" },
            });
            (record.contact_value || record.phone_normalized || '未留联系方式');
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
        if (column.key === 'region') {
            (record.region || '-');
        }
        if (column.key === 'status') {
            const __VLS_76 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
                color: (__VLS_ctx.leadStatusColor(record.status)),
            }));
            const __VLS_78 = __VLS_77({
                color: (__VLS_ctx.leadStatusColor(record.status)),
            }, ...__VLS_functionalComponentArgsRest(__VLS_77));
            __VLS_79.slots.default;
            (__VLS_ctx.leadStatusText(record.status));
            var __VLS_79;
        }
        if (column.key === 'missing_fields') {
            if (!record.missing_fields.length) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            }
            else {
                for (const [field] of __VLS_getVForSourceType((record.missing_fields))) {
                    const __VLS_80 = {}.ATag;
                    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                    // @ts-ignore
                    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
                        key: (field),
                        color: "orange",
                    }));
                    const __VLS_82 = __VLS_81({
                        key: (field),
                        color: "orange",
                    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
                    __VLS_83.slots.default;
                    (__VLS_ctx.missingFieldText(field));
                    var __VLS_83;
                }
            }
        }
        if (column.key === 'updated_at') {
            (__VLS_ctx.formatDateTime(record.updated_at));
        }
        if (column.key === 'action') {
            const __VLS_84 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }));
            const __VLS_86 = __VLS_85({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_85));
            let __VLS_88;
            let __VLS_89;
            let __VLS_90;
            const __VLS_91 = {
                onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.error))
                        return;
                    if (!(column.key === 'action'))
                        return;
                    __VLS_ctx.openDetail(record);
                }
            };
            __VLS_87.slots.default;
            var __VLS_87;
        }
    }
    var __VLS_67;
    const __VLS_92 = {}.ADrawer;
    /** @type {[typeof __VLS_components.ADrawer, typeof __VLS_components.aDrawer, typeof __VLS_components.ADrawer, typeof __VLS_components.aDrawer, ]} */ ;
    // @ts-ignore
    const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
        ...{ 'onClose': {} },
        title: "线索详情",
        open: (__VLS_ctx.detailVisible),
        width: (620),
    }));
    const __VLS_94 = __VLS_93({
        ...{ 'onClose': {} },
        title: "线索详情",
        open: (__VLS_ctx.detailVisible),
        width: (620),
    }, ...__VLS_functionalComponentArgsRest(__VLS_93));
    let __VLS_96;
    let __VLS_97;
    let __VLS_98;
    const __VLS_99 = {
        onClose: (...[$event]) => {
            if (!!(__VLS_ctx.error))
                return;
            __VLS_ctx.detailVisible = false;
        }
    };
    __VLS_95.slots.default;
    if (__VLS_ctx.detail) {
        const __VLS_100 = {}.ADescriptions;
        /** @type {[typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, ]} */ ;
        // @ts-ignore
        const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
            column: (1),
            size: "small",
            bordered: true,
        }));
        const __VLS_102 = __VLS_101({
            column: (1),
            size: "small",
            bordered: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_101));
        __VLS_103.slots.default;
        const __VLS_104 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
            label: "线索 ID",
        }));
        const __VLS_106 = __VLS_105({
            label: "线索 ID",
        }, ...__VLS_functionalComponentArgsRest(__VLS_105));
        __VLS_107.slots.default;
        (__VLS_ctx.detail.id);
        var __VLS_107;
        const __VLS_108 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
            label: "状态",
        }));
        const __VLS_110 = __VLS_109({
            label: "状态",
        }, ...__VLS_functionalComponentArgsRest(__VLS_109));
        __VLS_111.slots.default;
        const __VLS_112 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
            color: (__VLS_ctx.leadStatusColor(__VLS_ctx.detail.status)),
        }));
        const __VLS_114 = __VLS_113({
            color: (__VLS_ctx.leadStatusColor(__VLS_ctx.detail.status)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_113));
        __VLS_115.slots.default;
        (__VLS_ctx.leadStatusText(__VLS_ctx.detail.status));
        var __VLS_115;
        var __VLS_111;
        const __VLS_116 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
            label: "需求摘要",
        }));
        const __VLS_118 = __VLS_117({
            label: "需求摘要",
        }, ...__VLS_functionalComponentArgsRest(__VLS_117));
        __VLS_119.slots.default;
        (__VLS_ctx.detail.requirement_summary || '-');
        var __VLS_119;
        const __VLS_120 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
            label: "需求类型",
        }));
        const __VLS_122 = __VLS_121({
            label: "需求类型",
        }, ...__VLS_functionalComponentArgsRest(__VLS_121));
        __VLS_123.slots.default;
        (__VLS_ctx.detail.requirement_types.join('、') || '-');
        var __VLS_123;
        const __VLS_124 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
            label: "地域",
        }));
        const __VLS_126 = __VLS_125({
            label: "地域",
        }, ...__VLS_functionalComponentArgsRest(__VLS_125));
        __VLS_127.slots.default;
        (__VLS_ctx.detail.region || '-');
        var __VLS_127;
        const __VLS_128 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
            label: "缺失字段",
        }));
        const __VLS_130 = __VLS_129({
            label: "缺失字段",
        }, ...__VLS_functionalComponentArgsRest(__VLS_129));
        __VLS_131.slots.default;
        (__VLS_ctx.detail.missing_fields.map(__VLS_ctx.missingFieldText).join('、') || '-');
        var __VLS_131;
        const __VLS_132 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
            label: "客户姓名",
        }));
        const __VLS_134 = __VLS_133({
            label: "客户姓名",
        }, ...__VLS_functionalComponentArgsRest(__VLS_133));
        __VLS_135.slots.default;
        (__VLS_ctx.detail.customer_name || '-');
        var __VLS_135;
        const __VLS_136 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
            label: "公司名称",
        }));
        const __VLS_138 = __VLS_137({
            label: "公司名称",
        }, ...__VLS_functionalComponentArgsRest(__VLS_137));
        __VLS_139.slots.default;
        (__VLS_ctx.detail.company_name || '-');
        var __VLS_139;
        const __VLS_140 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
            label: "联系方式",
        }));
        const __VLS_142 = __VLS_141({
            label: "联系方式",
        }, ...__VLS_functionalComponentArgsRest(__VLS_141));
        __VLS_143.slots.default;
        (__VLS_ctx.detail.contact_value || __VLS_ctx.detail.phone_normalized || '-');
        var __VLS_143;
        const __VLS_144 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
            label: "智能体",
        }));
        const __VLS_146 = __VLS_145({
            label: "智能体",
        }, ...__VLS_functionalComponentArgsRest(__VLS_145));
        __VLS_147.slots.default;
        (__VLS_ctx.detail.agent_name || __VLS_ctx.detail.agent_code || '-');
        var __VLS_147;
        const __VLS_148 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
            label: "会话 ID",
        }));
        const __VLS_150 = __VLS_149({
            label: "会话 ID",
        }, ...__VLS_functionalComponentArgsRest(__VLS_149));
        __VLS_151.slots.default;
        (__VLS_ctx.detail.conversation_id || '-');
        var __VLS_151;
        const __VLS_152 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
            label: "事件数",
        }));
        const __VLS_154 = __VLS_153({
            label: "事件数",
        }, ...__VLS_functionalComponentArgsRest(__VLS_153));
        __VLS_155.slots.default;
        (__VLS_ctx.detail.event_count);
        var __VLS_155;
        const __VLS_156 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
            label: "创建时间",
        }));
        const __VLS_158 = __VLS_157({
            label: "创建时间",
        }, ...__VLS_functionalComponentArgsRest(__VLS_157));
        __VLS_159.slots.default;
        (__VLS_ctx.formatDateTime(__VLS_ctx.detail.created_at));
        var __VLS_159;
        const __VLS_160 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
            label: "更新时间",
        }));
        const __VLS_162 = __VLS_161({
            label: "更新时间",
        }, ...__VLS_functionalComponentArgsRest(__VLS_161));
        __VLS_163.slots.default;
        (__VLS_ctx.formatDateTime(__VLS_ctx.detail.updated_at));
        var __VLS_163;
        var __VLS_103;
        if (__VLS_ctx.detail.latest_event) {
            const __VLS_164 = {}.ADivider;
            /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
            // @ts-ignore
            const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({}));
            const __VLS_166 = __VLS_165({}, ...__VLS_functionalComponentArgsRest(__VLS_165));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
            const __VLS_168 = {}.ADescriptions;
            /** @type {[typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, ]} */ ;
            // @ts-ignore
            const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
                column: (1),
                size: "small",
                bordered: true,
            }));
            const __VLS_170 = __VLS_169({
                column: (1),
                size: "small",
                bordered: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_169));
            __VLS_171.slots.default;
            const __VLS_172 = {}.ADescriptionsItem;
            /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
            // @ts-ignore
            const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
                label: "事件状态",
            }));
            const __VLS_174 = __VLS_173({
                label: "事件状态",
            }, ...__VLS_functionalComponentArgsRest(__VLS_173));
            __VLS_175.slots.default;
            (__VLS_ctx.detail.latest_event.status);
            var __VLS_175;
            const __VLS_176 = {}.ADescriptionsItem;
            /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
            // @ts-ignore
            const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
                label: "动作",
            }));
            const __VLS_178 = __VLS_177({
                label: "动作",
            }, ...__VLS_functionalComponentArgsRest(__VLS_177));
            __VLS_179.slots.default;
            (__VLS_ctx.detail.latest_event.action || '-');
            var __VLS_179;
            const __VLS_180 = {}.ADescriptionsItem;
            /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
            // @ts-ignore
            const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
                label: "原因",
            }));
            const __VLS_182 = __VLS_181({
                label: "原因",
            }, ...__VLS_functionalComponentArgsRest(__VLS_181));
            __VLS_183.slots.default;
            (__VLS_ctx.detail.latest_event.reason || '-');
            var __VLS_183;
            const __VLS_184 = {}.ADescriptionsItem;
            /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
            // @ts-ignore
            const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({
                label: "调用记录",
            }));
            const __VLS_186 = __VLS_185({
                label: "调用记录",
            }, ...__VLS_functionalComponentArgsRest(__VLS_185));
            __VLS_187.slots.default;
            (__VLS_ctx.detail.latest_event.invocation_record_id || '-');
            var __VLS_187;
            const __VLS_188 = {}.ADescriptionsItem;
            /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
            // @ts-ignore
            const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
                label: "捕获时间",
            }));
            const __VLS_190 = __VLS_189({
                label: "捕获时间",
            }, ...__VLS_functionalComponentArgsRest(__VLS_189));
            __VLS_191.slots.default;
            (__VLS_ctx.formatDateTime(__VLS_ctx.detail.latest_event.created_at));
            var __VLS_191;
            var __VLS_171;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
                ...{ class: "json-block" },
            });
            (JSON.stringify(__VLS_ctx.detail.latest_event.normalized_delta, null, 2));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
                ...{ class: "json-block" },
            });
            (JSON.stringify(__VLS_ctx.detail.latest_event.followup_decision, null, 2));
        }
    }
    var __VLS_95;
}
/** @type {__VLS_StyleScopedClasses['page-block']} */ ;
/** @type {__VLS_StyleScopedClasses['page-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['page-subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-card']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-form']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-field']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-keyword']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-field']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-agent']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-field']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-region']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-field']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-status']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-field']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-contact']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-field']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-date']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-field']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-date']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['primary-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['tag-line']} */ ;
/** @type {__VLS_StyleScopedClasses['secondary-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['primary-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['secondary-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['primary-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['secondary-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['json-block']} */ ;
/** @type {__VLS_StyleScopedClasses['json-block']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            formatDateTime: formatDateTime,
            loading: loading,
            error: error,
            leads: leads,
            filter: filter,
            pagination: pagination,
            statusOptions: statusOptions,
            contactOptions: contactOptions,
            columns: columns,
            detailVisible: detailVisible,
            detail: detail,
            openDetail: openDetail,
            load: load,
            search: search,
            resetFilter: resetFilter,
            onTableChange: onTableChange,
            leadStatusColor: leadStatusColor,
            leadStatusText: leadStatusText,
            missingFieldText: missingFieldText,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
