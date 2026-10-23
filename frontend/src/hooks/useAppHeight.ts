"use client";

import { useEffect } from "react";

/**
 * 把 `--app-height` 跟着 visualViewport 的高度走（见 NavShell）。
 *
 * 手机上输入法弹出来时，**布局视口不会变小**——键盘是盖在页面上的，`100dvh` 还是原来的高度。
 * 结果就是：底部导航被顶到键盘后面，输入框和最后几条消息也被挡住，只能先把页面往上拖。
 * `visualViewport.height` 才是真正看得见的那块，外壳按它撑，键盘一开一收就跟着变。
 *
 * 桌面浏览器没有 visualViewport 差异（height 等于 innerHeight），CSS 里的 `100dvh` 兜底。
 */
export function useAppHeight() {
  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;

    const apply = () => {
      document.documentElement.style.setProperty("--app-height", `${Math.round(viewport.height)}px`);
    };

    apply();
    viewport.addEventListener("resize", apply);
    // iOS 上键盘弹出时页面会被悄悄滚一点，height 不变但 offsetTop 变了，scroll 事件里再量一次
    viewport.addEventListener("scroll", apply);

    return () => {
      viewport.removeEventListener("resize", apply);
      viewport.removeEventListener("scroll", apply);
      document.documentElement.style.removeProperty("--app-height");
    };
  }, []);
}
