"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");
exports.__esModule = true;
exports.default = void 0;
var _classnames = _interopRequireDefault(require("classnames"));
var React = _interopRequireWildcard(require("react"));
var _ThemeProvider = require("./ThemeProvider");
var _CardBody = _interopRequireDefault(require("./CardBody"));
var _CardFooter = _interopRequireDefault(require("./CardFooter"));
var _CardHeader = _interopRequireDefault(require("./CardHeader"));
var _CardImg = _interopRequireDefault(require("./CardImg"));
var _CardImgOverlay = _interopRequireDefault(require("./CardImgOverlay"));
var _CardLink = _interopRequireDefault(require("./CardLink"));
var _CardSubtitle = _interopRequireDefault(require("./CardSubtitle"));
var _CardText = _interopRequireDefault(require("./CardText"));
var _CardTitle = _interopRequireDefault(require("./CardTitle"));
var _jsxRuntime = require("react/jsx-runtime");
function _getRequireWildcardCache(nodeInterop) { if (typeof WeakMap !== "function") return null; var cacheBabelInterop = new WeakMap(); var cacheNodeInterop = new WeakMap(); return (_getRequireWildcardCache = function (nodeInterop) { return nodeInterop ? cacheNodeInterop : cacheBabelInterop; })(nodeInterop); }
function _interopRequireWildcard(obj, nodeInterop) { if (!nodeInterop && obj && obj.__esModule) { return obj; } if (obj === null || typeof obj !== "object" && typeof obj !== "function") { return { default: obj }; } var cache = _getRequireWildcardCache(nodeInterop); if (cache && cache.has(obj)) { return cache.get(obj); } var newObj = {}; var hasPropertyDescriptor = Object.defineProperty && Object.getOwnPropertyDescriptor; for (var key in obj) { if (key !== "default" && Object.prototype.hasOwnProperty.call(obj, key)) { var desc = hasPropertyDescriptor ? Object.getOwnPropertyDescriptor(obj, key) : null; if (desc && (desc.get || desc.set)) { Object.defineProperty(newObj, key, desc); } else { newObj[key] = obj[key]; } } } newObj.default = obj; if (cache) { cache.set(obj, newObj); } return newObj; }
const Card = /*#__PURE__*/React.forwardRef(({
  bsPrefix,
  className,
  bg,
  text,
  border,
  body = false,
  children,
  // Need to define the default "as" during prop destructuring to be compatible with styled-components github.com/react-bootstrap/react-bootstrap/issues/3595
  as: Component = 'div',
  ...props
}, ref) => {
  const prefix = (0, _ThemeProvider.useBootstrapPrefix)(bsPrefix, 'card');
  return /*#__PURE__*/(0, _jsxRuntime.jsx)(Component, {
    ref: ref,
    ...props,
    className: (0, _classnames.default)(className, prefix, bg && `bg-${bg}`, text && `text-${text}`, border && `border-${border}`),
    children: body ? /*#__PURE__*/(0, _jsxRuntime.jsx)(_CardBody.default, {
      children: children
    }) : children
  });
});
Card.displayName = 'Card';
var _default = Object.assign(Card, {
  Img: _CardImg.default,
  Title: _CardTitle.default,
  Subtitle: _CardSubtitle.default,
  Body: _CardBody.default,
  Link: _CardLink.default,
  Text: _CardText.default,
  Header: _CardHeader.default,
  Footer: _CardFooter.default,
  ImgOverlay: _CardImgOverlay.default
});
exports.default = _default;
module.exports = exports.default;