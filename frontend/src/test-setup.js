// jsdom não tem estas APIs, que o Vuetify usa.
globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
globalThis.visualViewport = globalThis.visualViewport ?? { addEventListener() {}, removeEventListener() {}, width: 1280, height: 800 }
window.matchMedia = window.matchMedia ?? ((q) => ({ matches: true, media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} }))
