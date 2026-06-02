/**
 * 将日期字符串或 Date 格式化为 YYYY-MM-DD HH:mm:ss。
 * 空值返回 "-"。
 */
export function formatDateTime(value) {
    if (!value)
        return '-';
    const d = value instanceof Date ? value : new Date(value);
    if (isNaN(d.getTime()))
        return '-';
    const pad = (n) => String(n).padStart(2, '0');
    return (`${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
        `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`);
}
/**
 * 将 Date 转为 ISO 8601 字符串（用于 API 查询参数）。
 * 支持 Date、Dayjs、string 类型。
 */
export function toISOString(value) {
    if (!value)
        return undefined;
    if (value instanceof Date)
        return value.toISOString();
    if (typeof value === 'string')
        return value;
    // Dayjs 对象：调用其 toISOString() 方法
    if (typeof value === 'object' && 'toISOString' in value && typeof value.toISOString === 'function') {
        return value.toISOString();
    }
    return undefined;
}
