/** 认证 API：登录、查看当前用户、刷新 token、登出。 */
import { http } from './http';
export async function login(payload) {
    const { data } = await http.post('/auth/login', payload);
    return data;
}
export async function getMe() {
    const { data } = await http.get('/auth/me');
    return data;
}
export async function getSessionStatus() {
    const { data } = await http.get('/auth/session');
    return data;
}
export async function refreshSession() {
    const { data } = await http.post('/auth/refresh');
    return data;
}
export async function logout() {
    await http.post('/auth/logout');
}
