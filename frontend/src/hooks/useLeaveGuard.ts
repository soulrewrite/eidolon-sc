"use client";

import { useEffect } from "react";

/**
 * 通话中离开页面时先问一句（beforeunload）。
 *
 * 通话是挂在页面上的：刷新、关标签页、点外链都会直接把通话掐掉，没有任何提示。
 * 通话进行中挂上这个监听，浏览器会弹它自己那句「确定要离开吗」——文案改不了，
 * 但至少不会一点就走、回来发现她已经挂了。
 *
 * 手机上切到别的 App（visibilitychange）拦不住，也提示不了，所以只管真正的「离开」。
 */
export function useLeaveGuard(active: boolean) {
  useEffect(() => {
    if (!active) return;

    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      // 现代浏览器忽略自定义文案，两样都要给：preventDefault 让 Chrome 生效，returnValue 照顾旧内核
      event.preventDefault();
      event.returnValue = "";
    };

    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [active]);
}
