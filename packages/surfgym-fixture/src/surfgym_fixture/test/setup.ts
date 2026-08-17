class TestPath2D {
  addPath() {}
  arc() {}
  arcTo() {}
  bezierCurveTo() {}
  closePath() {}
  ellipse() {}
  lineTo() {}
  moveTo() {}
  quadraticCurveTo() {}
  rect() {}
  roundRect() {}
}

Object.defineProperty(globalThis, "Path2D", {
  configurable: true,
  value: TestPath2D,
});

if (typeof HTMLCanvasElement !== "undefined") {
  Object.defineProperty(HTMLCanvasElement.prototype, "getContext", {
    configurable: true,
    value: () => ({}),
  });
}
