"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");
exports.__esModule = true;
exports.default = void 0;
var React = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
var _ThemeProvider = require("./ThemeProvider");
var _divWithClassName = _interopRequireDefault(require("./divWithClassName"));
var _jsxRuntime = require("react/jsx-runtime");
function _getRequireWildcardCache(nodeInterop) { if (typeof WeakMap !== "function") return null; var cacheBabelInterop = new WeakMap(); var cacheNodeInterop = new WeakMap(); return (_getRequireWildcardCache = function (nodeInterop) { return nodeInterop ? cacheNodeInterop : cacheBabelInterop; })(nodeInterop); }
function _interopRequireWildcard(obj, nodeInterop) { if (!nodeInterop && obj && obj.__esModule) { return obj; } if (obj === null || typeof obj !== "object" && typeof obj !== "function") { return { default: obj }; } var cache = _getRequireWildcardCache(nodeInterop); if (cache && cache.has(obj)) { return cache.get(obj); } var newObj = {}; var hasPropertyDescriptor = Object.defineProperty && Object.getOwnPropertyDescriptor; for (var key in obj) { if (key !== "default" && Object.prototype.hasOwnProperty.call(obj, key)) { var desc = hasPropertyDescriptor ? Object.getOwnPropertyDescriptor(obj, key) : null; if (desc && (desc.get || desc.set)) { Object.defineProperty(newObj, key, desc); } else { newObj[key] = obj[key]; } } } newObj.default = obj; if (cache) { cache.set(obj, newObj); } return newObj; }
const DivStyledAsH5 = (0, _divWithClassName.default)('h5');
const CardTitle = /*#__PURE__*/React.forwardRef(({
  className,
  bsPrefix,
  as: Component = DivStyledAsH5,
  ...props
}, ref) => {
  bsPrefix = (0, _ThemeProvider.useBootstrapPrefix)(bsPrefix, 'card-title');
  return /*#__PURE__*/(0, _jsxRuntime.jsx)(Component, {
    ref: ref,
    className: (0, _classnames.default)(className, bsPrefix),
    ...props
  });
});
CardTitle.displayName = 'CardTitle';
var _default = CardTitle;
exports.default = _default;
module.exports = exports.default;