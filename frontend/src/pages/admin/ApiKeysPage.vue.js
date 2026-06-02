import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { issueApiKeyByPhone, listApiKeys } from '../../api/admin';
import { formatDateTime } from '../../utils/format';
const loading = ref(false);
const error = ref(false);
const issuing = ref(false);
const items = ref([]);
const phone = ref('');
const keyName = ref('customer-key');
const issuedKey = ref('');
const tablePagination = reactive({
    current: 1,
    pageSize: 10,
    pageSizeOptions: ['10', '20', '50'],
    showSizeChanger: true,
    size: 'small',
    showTotal: (t) => `共 ${t} 条`,
    onShowSizeChange: (_current, size) => {
        tablePagination.current = 1;
        tablePagination.pageSize = size;
    },
});
const columns = [
    { title: '客户', key: 'customer', width: 210 },
    { title: 'Key 前缀', dataIndex: 'key_prefix', key: 'key_prefix', width: 130 },
    { title: '权限范围', key: 'scopes', width: 150 },
    { title: '状态', key: 'status', width: 90 },
    { title: '最近使用', dataIndex: 'last_used_at', key: 'last_used_at', width: 170 },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
];
function keyStatusColor(status) {
    const map = {
        ACTIVE: 'green',
        DISABLED: 'orange',
        EXPIRED: 'red',
        REVOKED: 'red',
    };
    return map[status] ?? 'default';
}
function keyStatusText(status) {
    const map = {
        ACTIVE: '启用',
        DISABLED: '禁用',
        EXPIRED: '过期',
        REVOKED: '撤销',
    };
    return map[status] ?? status;
}
function scopeText(scope) {
    const map = {
        invoke: '调用',
        read: '读取',
        manage: '管理',
        '*': '全部',
    };
    return map[scope] ?? scope;
}
async function load() {
    loading.value = true;
    error.value = false;
    try {
        items.value = await listApiKeys();
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
async function issue() {
    issuing.value = true;
    try {
        const result = await issueApiKeyByPhone({
            phone: phone.value.trim(),
            name: keyName.value,
            scopes: ['invoke'],
        });
        issuedKey.value = result.api_key;
        await load();
    }
    catch {
        // 错误由 http 层处理
    }
    finally {
        issuing.value = false;
    }
}
async function copyKey() {
    await navigator.clipboard.writeText(issuedKey.value);
    message.success('已复制到剪贴板');
}
onMounted(load);
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
const __VLS_0 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    title: "按手机号签发 API Key",
    size: "small",
    ...{ class: "issue-card" },
}));
const __VLS_2 = __VLS_1({
    title: "按手机号签发 API Key",
    size: "small",
    ...{ class: "issue-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ 'onFinish': {} },
    layout: "inline",
}));
const __VLS_6 = __VLS_5({
    ...{ 'onFinish': {} },
    layout: "inline",
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
let __VLS_8;
let __VLS_9;
let __VLS_10;
const __VLS_11 = {
    onFinish: (__VLS_ctx.issue)
};
__VLS_7.slots.default;
const __VLS_12 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    label: "手机号",
    required: true,
}));
const __VLS_14 = __VLS_13({
    label: "手机号",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
const __VLS_16 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    value: (__VLS_ctx.phone),
    placeholder: "外部客户手机号",
}));
const __VLS_18 = __VLS_17({
    value: (__VLS_ctx.phone),
    placeholder: "外部客户手机号",
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
var __VLS_15;
const __VLS_20 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    label: "Key 名称",
    required: true,
}));
const __VLS_22 = __VLS_21({
    label: "Key 名称",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_23.slots.default;
const __VLS_24 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    value: (__VLS_ctx.keyName),
    placeholder: "便于识别的名称",
}));
const __VLS_26 = __VLS_25({
    value: (__VLS_ctx.keyName),
    placeholder: "便于识别的名称",
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
var __VLS_23;
const __VLS_28 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({}));
const __VLS_30 = __VLS_29({}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
const __VLS_32 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    type: "primary",
    htmlType: "submit",
    loading: (__VLS_ctx.issuing),
}));
const __VLS_34 = __VLS_33({
    type: "primary",
    htmlType: "submit",
    loading: (__VLS_ctx.issuing),
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_35.slots.default;
var __VLS_35;
var __VLS_31;
var __VLS_7;
if (__VLS_ctx.issuedKey) {
    const __VLS_36 = {}.AAlert;
    /** @type {[typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, ]} */ ;
    // @ts-ignore
    const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
        ...{ 'onClose': {} },
        type: "success",
        showIcon: true,
        closable: true,
        ...{ class: "issued-alert" },
    }));
    const __VLS_38 = __VLS_37({
        ...{ 'onClose': {} },
        type: "success",
        showIcon: true,
        closable: true,
        ...{ class: "issued-alert" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_37));
    let __VLS_40;
    let __VLS_41;
    let __VLS_42;
    const __VLS_43 = {
        onClose: (...[$event]) => {
            if (!(__VLS_ctx.issuedKey))
                return;
            __VLS_ctx.issuedKey = '';
        }
    };
    __VLS_39.slots.default;
    {
        const { message: __VLS_thisSlot } = __VLS_39.slots;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        const __VLS_44 = {}.AInputPassword;
        /** @type {[typeof __VLS_components.AInputPassword, typeof __VLS_components.aInputPassword, ]} */ ;
        // @ts-ignore
        const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
            ...{ 'onFocus': {} },
            value: (__VLS_ctx.issuedKey),
            readonly: true,
            ...{ class: "key-display" },
        }));
        const __VLS_46 = __VLS_45({
            ...{ 'onFocus': {} },
            value: (__VLS_ctx.issuedKey),
            readonly: true,
            ...{ class: "key-display" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_45));
        let __VLS_48;
        let __VLS_49;
        let __VLS_50;
        const __VLS_51 = {
            onFocus: (...[$event]) => {
                if (!(__VLS_ctx.issuedKey))
                    return;
                $event.target.select();
            }
        };
        var __VLS_47;
        const __VLS_52 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
            ...{ 'onClick': {} },
            size: "small",
            type: "primary",
            ghost: true,
        }));
        const __VLS_54 = __VLS_53({
            ...{ 'onClick': {} },
            size: "small",
            type: "primary",
            ghost: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_53));
        let __VLS_56;
        let __VLS_57;
        let __VLS_58;
        const __VLS_59 = {
            onClick: (__VLS_ctx.copyKey)
        };
        __VLS_55.slots.default;
        var __VLS_55;
    }
    var __VLS_39;
}
var __VLS_3;
if (__VLS_ctx.error) {
    const __VLS_60 = {}.AResult;
    /** @type {[typeof __VLS_components.AResult, typeof __VLS_components.aResult, typeof __VLS_components.AResult, typeof __VLS_components.aResult, ]} */ ;
    // @ts-ignore
    const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
        status: "error",
        title: "加载失败",
        subTitle: "无法获取 API Key 列表",
        ...{ style: {} },
    }));
    const __VLS_62 = __VLS_61({
        status: "error",
        title: "加载失败",
        subTitle: "无法获取 API Key 列表",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_61));
    __VLS_63.slots.default;
    {
        const { extra: __VLS_thisSlot } = __VLS_63.slots;
        const __VLS_64 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
            ...{ 'onClick': {} },
            type: "primary",
        }));
        const __VLS_66 = __VLS_65({
            ...{ 'onClick': {} },
            type: "primary",
        }, ...__VLS_functionalComponentArgsRest(__VLS_65));
        let __VLS_68;
        let __VLS_69;
        let __VLS_70;
        const __VLS_71 = {
            onClick: (__VLS_ctx.load)
        };
        __VLS_67.slots.default;
        var __VLS_67;
    }
    var __VLS_63;
}
else if (__VLS_ctx.items.length === 0 && !__VLS_ctx.loading) {
    const __VLS_72 = {}.AEmpty;
    /** @type {[typeof __VLS_components.AEmpty, typeof __VLS_components.aEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
        description: "暂无 API Key，在上方按手机号签发",
        ...{ style: {} },
    }));
    const __VLS_74 = __VLS_73({
        description: "暂无 API Key，在上方按手机号签发",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_73));
}
else {
    const __VLS_76 = {}.ATable;
    /** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
        ...{ 'onChange': {} },
        columns: (__VLS_ctx.columns),
        dataSource: (__VLS_ctx.items),
        loading: (__VLS_ctx.loading),
        pagination: (__VLS_ctx.tablePagination),
        rowKey: "id",
        size: "middle",
        ...{ style: {} },
    }));
    const __VLS_78 = __VLS_77({
        ...{ 'onChange': {} },
        columns: (__VLS_ctx.columns),
        dataSource: (__VLS_ctx.items),
        loading: (__VLS_ctx.loading),
        pagination: (__VLS_ctx.tablePagination),
        rowKey: "id",
        size: "middle",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_77));
    let __VLS_80;
    let __VLS_81;
    let __VLS_82;
    const __VLS_83 = {
        onChange: (__VLS_ctx.onTableChange)
    };
    __VLS_79.slots.default;
    {
        const { bodyCell: __VLS_thisSlot } = __VLS_79.slots;
        const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
        if (column.key === 'status') {
            const __VLS_84 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
                color: (__VLS_ctx.keyStatusColor(record.status)),
            }));
            const __VLS_86 = __VLS_85({
                color: (__VLS_ctx.keyStatusColor(record.status)),
            }, ...__VLS_functionalComponentArgsRest(__VLS_85));
            __VLS_87.slots.default;
            (__VLS_ctx.keyStatusText(record.status));
            var __VLS_87;
        }
        if (column.key === 'customer') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "primary-cell" },
            });
            (record.issued_for_phone || '-');
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "secondary-cell" },
            });
            (record.name);
        }
        if (column.key === 'scopes') {
            for (const [s] of __VLS_getVForSourceType((record.scopes))) {
                const __VLS_88 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
                    key: (s),
                    ...{ style: {} },
                }));
                const __VLS_90 = __VLS_89({
                    key: (s),
                    ...{ style: {} },
                }, ...__VLS_functionalComponentArgsRest(__VLS_89));
                __VLS_91.slots.default;
                (__VLS_ctx.scopeText(s));
                var __VLS_91;
            }
        }
        if (column.key === 'key_prefix') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "mono-cell" },
            });
            (record.key_prefix);
        }
        if (column.key === 'created_at') {
            (__VLS_ctx.formatDateTime(record.created_at));
        }
        if (column.key === 'last_used_at') {
            (__VLS_ctx.formatDateTime(record.last_used_at));
        }
    }
    var __VLS_79;
}
/** @type {__VLS_StyleScopedClasses['page-block']} */ ;
/** @type {__VLS_StyleScopedClasses['page-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['page-subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['issue-card']} */ ;
/** @type {__VLS_StyleScopedClasses['issued-alert']} */ ;
/** @type {__VLS_StyleScopedClasses['key-display']} */ ;
/** @type {__VLS_StyleScopedClasses['primary-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['secondary-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['mono-cell']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            formatDateTime: formatDateTime,
            loading: loading,
            error: error,
            issuing: issuing,
            items: items,
            phone: phone,
            keyName: keyName,
            issuedKey: issuedKey,
            tablePagination: tablePagination,
            columns: columns,
            keyStatusColor: keyStatusColor,
            keyStatusText: keyStatusText,
            scopeText: scopeText,
            load: load,
            onTableChange: onTableChange,
            issue: issue,
            copyKey: copyKey,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
