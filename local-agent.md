initialize_command: ./setup.py build
initialize_command: ./setup.py gui
copy_resource: .build-cache
copy_resource: .cache
copy_resource: .ruff_cache
copy_resource: translations
copy_resource: resources

# System Instructions & Project Context

## Project Architecture & Stack
This is a multi-language repository. Adhere strictly to the idiomatic styling, patterns, and type safety of each respective language ecosystem present in the codebase. Do not mix patterns across language boundaries.

## Rules for Code Generation
- **Type Safety**: Enforce strict typing. Never use `any` or loose types.
- **Error Handling**: Implement explicit error handling. Avoid silent failures or empty catch blocks.
- **Dependency Minimization**: Use existing project utilities and native standard libraries before suggesting new external packages.
- **Local Context**: Search the codebase for existing patterns before writing boilerplate structure from scratch.

## Project Execution Workflows
You must always use the following custom scripts to build, verify, and test changes. Do not use generic toolchains such as `pytest`. 

### 🛠️ Build Commands
Execute this command to compile all modules and check for syntax or type errors:
```bash
./setup.py build
```

### 🧪 Test Commands
Execute this command to run the test suite across all language domains:
```bash
./setup.py test
```

To isolate testing to a specific test use, use the test name without the leading
"test" prefix. For example, to run a python test named test_my_function, use
```bash
./setup.py test my_function
```

## Verification Pipeline
Before declaring a task complete, you must follow this exact verification lifecycle:
1. Run the local **Build Command** to guarantee zero compilation or compilation-stage type errors.
2. Run the local **Test Command** 
3. If errors occur, analyze the output logs completely before writing a fix. Do not guess.
4. Run `ruff check --fix` on yout changed python files to ensure your generated code is pep8 compliant
