import * as React from 'react';
import { type FormCheckInputProps } from './FormCheckInput';
import { BsPrefixProps, BsPrefixRefForwardingComponent } from './helpers';
export interface InputGroupProps extends BsPrefixProps, React.HTMLAttributes<HTMLElement> {
    size?: 'sm' | 'lg';
    hasValidation?: boolean;
}
declare const _default: BsPrefixRefForwardingComponent<"div", InputGroupProps> & {
    Text: BsPrefixRefForwardingComponent<"span", import("./InputGroupText").InputGroupTextProps>;
    Radio: (props: FormCheckInputProps) => JSX.Element;
    Checkbox: (props: FormCheckInputProps) => JSX.Element;
};
export default _default;
