// Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
// Node 25 的实验性 Web Storage 与浏览器模拟环境分离。
Object.defineProperty(globalThis, 'localStorage', { value: window.localStorage, configurable: true })
