/**
 * ESLint flat config for Novum frontend.
 * Enforces Atomic Design layering per ui-prototype.md §8.4.
 *
 * Layer rules (strict downward dependency):
 * - Atoms: only ui/ primitives and tokens
 * - Molecules: atoms + tokens only
 * - Organisms: atoms + molecules + hooks
 * - Templates: organisms + atoms + layout primitives
 * - Pages: anything below + hooks + stores + routing
 */

import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactPlugin from "eslint-plugin-react";
import reactHooksPlugin from "eslint-plugin-react-hooks";
import importPlugin from "eslint-plugin-import";

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.strictTypeChecked,
  {
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },
  {
    files: ["**/*.{ts,tsx}"],
    plugins: {
      react: reactPlugin,
      "react-hooks": reactHooksPlugin,
      import: importPlugin,
    },
    settings: {
      react: {
        version: "detect",
      },
      "import/resolver": {
        typescript: {
          alwaysTryTypes: true,
        },
      },
    },
    rules: {
      // React rules
      "react/react-in-jsx-scope": "off",
      "react/prop-types": "off",
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",

      // TypeScript rules
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/explicit-function-return-type": "off",
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/no-misused-promises": "error",

      // Import rules for Atomic Design enforcement
      "import/no-restricted-paths": [
        "error",
        {
          zones: [
            // Atoms cannot import from molecules, organisms, templates, or pages
            {
              target: "./src/components/atoms/**/*",
              from: "./src/components/molecules/**/*",
              message: "Atoms cannot import from molecules (Atomic Design §8.1)",
            },
            {
              target: "./src/components/atoms/**/*",
              from: "./src/components/organisms/**/*",
              message: "Atoms cannot import from organisms (Atomic Design §8.1)",
            },
            {
              target: "./src/components/atoms/**/*",
              from: "./src/components/templates/**/*",
              message: "Atoms cannot import from templates (Atomic Design §8.1)",
            },
            {
              target: "./src/components/atoms/**/*",
              from: "./src/pages/**/*",
              message: "Atoms cannot import from pages (Atomic Design §8.1)",
            },

            // Molecules cannot import from organisms, templates, or pages
            {
              target: "./src/components/molecules/**/*",
              from: "./src/components/organisms/**/*",
              message: "Molecules cannot import from organisms (Atomic Design §8.1)",
            },
            {
              target: "./src/components/molecules/**/*",
              from: "./src/components/templates/**/*",
              message: "Molecules cannot import from templates (Atomic Design §8.1)",
            },
            {
              target: "./src/components/molecules/**/*",
              from: "./src/pages/**/*",
              message: "Molecules cannot import from pages (Atomic Design §8.1)",
            },

            // Organisms cannot import from templates or pages
            {
              target: "./src/components/organisms/**/*",
              from: "./src/components/templates/**/*",
              message: "Organisms cannot import from templates (Atomic Design §8.1)",
            },
            {
              target: "./src/components/organisms/**/*",
              from: "./src/pages/**/*",
              message: "Organisms cannot import from pages (Atomic Design §8.1)",
            },

            // Templates cannot import from pages
            {
              target: "./src/components/templates/**/*",
              from: "./src/pages/**/*",
              message: "Templates cannot import from pages (Atomic Design §8.1)",
            },

            // No data fetching outside pages - hooks that fetch are only in pages
            {
              target: "./src/components/atoms/**/*",
              from: "./src/hooks/useRun*",
              message: "Data fetching hooks only allowed in pages (Atomic Design §8.1)",
            },
            {
              target: "./src/components/molecules/**/*",
              from: "./src/hooks/useRun*",
              message: "Data fetching hooks only allowed in pages (Atomic Design §8.1)",
            },
            {
              target: "./src/components/organisms/**/*",
              from: "./src/hooks/useRun*",
              message: "Data fetching hooks only allowed in pages (Atomic Design §8.1)",
            },
            {
              target: "./src/components/templates/**/*",
              from: "./src/hooks/useRun*",
              message: "Data fetching hooks only allowed in pages (Atomic Design §8.1)",
            },
          ],
        },
      ],

      // One component per file (enforced by convention, warning only)
      "import/no-default-export": "off", // Pages and lazy loading need default exports
    },
  },
  {
    // Allow console in development
    files: ["**/*.{ts,tsx}"],
    rules: {
      "no-console": ["warn", { allow: ["warn", "error"] }],
    },
  },
  {
    // Ignore generated files
    ignores: [
      "dist/**",
      "node_modules/**",
      "*.config.js",
      "*.config.ts",
      "src/components/ui/**", // shadcn/ui generated components
    ],
  }
);
