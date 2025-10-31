import { ButtonHTMLAttributes, DetailedHTMLProps } from "react";

interface Props extends DetailedHTMLProps<ButtonHTMLAttributes<HTMLButtonElement>, HTMLButtonElement> {
  className?: string;
  children: React.ReactNode;
}

export function Button({ children, className = "", ...props }: Props) {
  return (
    <button className={`px-3 py-1 rounded text-sm font-medium ${className}`} {...props}>
      {children}
    </button>
  );
}