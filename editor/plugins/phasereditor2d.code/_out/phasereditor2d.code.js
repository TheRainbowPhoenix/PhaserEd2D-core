var phasereditor2d;
(function (phasereditor2d) {
    var code;
    (function (code) {
        var controls = colibri.ui.controls;
        var io = colibri.core.io;
        code.ICON_SYMBOL_CLASS = "symbol-class";
        code.ICON_SYMBOL_CONSTANT = "symbol-constant";
        code.ICON_SYMBOL_FIELD = "symbol-field";
        code.ICON_SYMBOL_INTERFACE = "symbol-interface";
        code.ICON_SYMBOL_METHOD = "symbol-method";
        code.ICON_SYMBOL_NAMESPACE = "symbol-namespace";
        code.ICON_SYMBOL_PROPERTY = "symbol-property";
        code.ICON_SYMBOL_VARIABLE = "symbol-variable";
        class CodePlugin extends colibri.Plugin {
            constructor() {
                super("phasereditor2d.code");
            }
            static getInstance() {
                if (!this._instance) {
                    this._instance = new CodePlugin();
                }
                return this._instance;
            }
            registerExtensions(reg) {
                // icons loader
                reg.addExtension(colibri.ui.ide.IconLoaderExtension.withPluginFiles(this, [
                    code.ICON_SYMBOL_CLASS,
                    code.ICON_SYMBOL_CONSTANT,
                    code.ICON_SYMBOL_FIELD,
                    code.ICON_SYMBOL_INTERFACE,
                    code.ICON_SYMBOL_METHOD,
                    code.ICON_SYMBOL_NAMESPACE,
                    code.ICON_SYMBOL_PROPERTY,
                    code.ICON_SYMBOL_VARIABLE
                ]));
                // editors
                reg.addExtension(new colibri.ui.ide.EditorExtension([
                    code.ui.editors.JavaScriptEditor.getJavaScriptFactory(),
                    code.ui.editors.JavaScriptEditor.getTypeScriptFactory(),
                    code.ui.editors.HTMLEditor.getFactory(),
                    code.ui.editors.CSSEditor.getFactory(),
                    code.ui.editors.JSONEditor.getFactory(),
                    code.ui.editors.XMLEditor.getFactory(),
                    code.ui.editors.TextEditor.getFactory(),
                ]));
                // default editor factory
                colibri.Platform.getWorkbench().getEditorRegistry().registerDefaultFactory(code.ui.editors.TextEditor.getFactory());
                // extra libs loader
                monaco.languages.typescript.javascriptDefaults.setEagerModelSync(true);
                // reg.addExtension(new ui.PreloadExtraLibsExtension());
                reg.addExtension(new code.ui.PreloadModelsExtension());
                reg.addExtension(new code.ui.PreloadJavaScriptWorkerExtension());
            }
            async getJavaScriptWorker() {
                if (this._javaScriptWorker) {
                    return this._javaScriptWorker;
                }
                const getWorker = await monaco.languages.typescript.getJavaScriptWorker();
                this._javaScriptWorker = await getWorker();
                return this._javaScriptWorker;
            }
            static fileUri(file) {
                if (file instanceof io.FilePath) {
                    return monaco.Uri.file(file.getFullName());
                }
                return monaco.Uri.file(file);
            }
            getModelManager() {
                return this._modelManager;
            }
            async starting() {
                this._modelManager = new code.ui.ModelManager();
                // theme
                monaco.editor.defineTheme("vs", {
                    inherit: true,
                    base: "vs",
                    rules: [
                        {
                            background: "e2e2e2"
                        }
                    ],
                    colors: {
                        "editor.background": "#eaeaea",
                        "editor.lineHighlightBackground": "#bad4ee88"
                    }
                });
                monaco.editor.defineTheme("vs-dark", {
                    inherit: true,
                    base: "vs-dark",
                    rules: [
                        {
                            background: "222222"
                        }
                    ],
                    colors: {
                        "editor.background": "#2e2e2e",
                        "editor.lineHighlightBackground": "#3e3e3e88"
                    }
                });
                colibri.Platform.getWorkbench().eventThemeChanged.addListener(() => {
                    let monacoTheme = "vs";
                    if (controls.Controls.getTheme().dark) {
                        monacoTheme = "vs-dark";
                    }
                    monaco.editor.setTheme(monacoTheme);
                });
                this.customizeMonaco();
            }
            customizeMonaco() {
                const opts = monaco.languages.typescript.javascriptDefaults.getCompilerOptions();
                opts.target = monaco.languages.typescript.ScriptTarget.ESNext;
                opts.module = monaco.languages.typescript.ModuleKind.ESNext;
                this.customizeCodeServiceImpl();
            }
            customizeCodeServiceImpl() {
                const require = window["require"];
                const module = require("vs/editor/standalone/browser/standaloneCodeServiceImpl");
                const StandaloneCodeEditorServiceImpl = module.StandaloneCodeEditorServiceImpl;
                StandaloneCodeEditorServiceImpl.prototype.openCodeEditor =
                    (input, editor, sideBySide) => {
                        const uri = input.resource;
                        const fileName = uri.path.substring(1);
                        const file = colibri.ui.ide.FileUtils.getFileFromPath(fileName);
                        if (file) {
                            const editorPart = colibri.Platform
                                .getWorkbench().openEditor(file);
                            if (!editorPart) {
                                return;
                            }
                            // TODO: for now, but the right way is to pass a "RevealElement" in the .openEditor() method
                            setTimeout(() => {
                                const newEditor = editorPart.getMonacoEditor();
                                const selection = input.options ? input.options.selection : null;
                                if (selection) {
                                    if (typeof selection.endLineNumber === "number"
                                        && typeof selection.endColumn === "number") {
                                        newEditor.setSelection(selection);
                                        newEditor.revealRangeInCenter(selection, monaco.editor.ScrollType.Immediate);
                                    }
                                    else {
                                        const pos = {
                                            lineNumber: selection.startLineNumber,
                                            column: selection.startColumn
                                        };
                                        newEditor.setPosition(pos);
                                        newEditor.revealPositionInCenter(pos, monaco.editor.ScrollType.Immediate);
                                    }
                                }
                            }, 10);
                        }
                        else {
                            alert("File not found '" + fileName + "'");
                        }
                        return Promise.resolve(editor);
                    };
            }
        }
        code.CodePlugin = CodePlugin;
        colibri.Platform.addPlugin(CodePlugin.getInstance());
    })(code = phasereditor2d.code || (phasereditor2d.code = {}));
})(phasereditor2d || (phasereditor2d = {}));
var phasereditor2d;
(function (phasereditor2d) {
    var code;
    (function (code) {
        var ui;
        (function (ui) {
            class ModelManager {
                constructor() {
                    const utils = colibri.ui.ide.FileUtils;
                    const storage = colibri.ui.ide.Workbench.getWorkbench().getFileStorage();
                    storage.addFirstChangeListener(async (e) => {
                        const files = utils.getRoot().flatTree([], false);
                        const fileMap = new Map();
                        for (const file of files) {
                            fileMap.set(file.getFullName(), file);
                        }
                        // handle additions
                        for (const fileName of e.getAddRecords()) {
                            if (!ModelManager.handleFileName(fileName)) {
                                continue;
                            }
                            const file = fileMap.get(fileName);
                            const str = await utils.preloadAndGetFileString(file);
                            const lang = this.getModeId(fileName);
                            monaco.editor.createModel(str, lang, code.CodePlugin.fileUri(fileName));
                        }
                        // handle deletions
                        for (const fileName of e.getDeleteRecords()) {
                            if (!ModelManager.handleFileName(fileName)) {
                                continue;
                            }
                            const model = monaco.editor.getModel(code.CodePlugin.fileUri(fileName));
                            if (model) {
                                model.dispose();
                            }
                        }
                        // handle modifications
                        for (const fileName of e.getModifiedRecords()) {
                            if (!ModelManager.handleFileName(fileName)) {
                                continue;
                            }
                            const file = fileMap.get(fileName);
                            const content = await utils.preloadAndGetFileString(file);
                            const model = monaco.editor.getModel(code.CodePlugin.fileUri(fileName));
                            if (model.getValue() !== content) {
                                model.setValue(content);
                            }
                        }
                        // handle renames
                        for (const oldFileName of e.getRenameFromRecords()) {
                            if (!ModelManager.handleFileName(oldFileName)) {
                                continue;
                            }
                            const newFileName = e.getRenameTo(oldFileName);
                            const oldModel = monaco.editor.getModel(code.CodePlugin.fileUri(oldFileName));
                            const lang = this.getModeId(newFileName);
                            monaco.editor.createModel(oldModel.getValue(), lang, code.CodePlugin.fileUri(newFileName));
                            oldModel.dispose();
                        }
                    });
                }
                getModeId(filename) {
                    return filename.endsWith(".js") ? "javascript" : "typescript";
                }
                static handleFileName(filename) {
                    return filename.endsWith(".js") || filename.endsWith(".ts");
                }
            }
            ui.ModelManager = ModelManager;
        })(ui = code.ui || (code.ui = {}));
    })(code = phasereditor2d.code || (phasereditor2d.code = {}));
})(phasereditor2d || (phasereditor2d = {}));
var phasereditor2d;
(function (phasereditor2d) {
    var code;
    (function (code) {
        var ui;
        (function (ui) {
            class PreloadJavaScriptWorkerExtension extends colibri.ui.ide.PreloadProjectResourcesExtension {
                async computeTotal() {
                    return 1;
                }
                async preload(monitor) {
                    try {
                        await code.CodePlugin.getInstance().getJavaScriptWorker();
                    }
                    catch (e) {
                        console.error(e);
                    }
                    monitor.step();
                }
            }
            ui.PreloadJavaScriptWorkerExtension = PreloadJavaScriptWorkerExtension;
        })(ui = code.ui || (code.ui = {}));
    })(code = phasereditor2d.code || (phasereditor2d.code = {}));
})(phasereditor2d || (phasereditor2d = {}));
var phasereditor2d;
(function (phasereditor2d) {
    var code;
    (function (code) {
        var ui;
        (function (ui) {
            class PreloadModelsExtension extends colibri.ui.ide.PreloadProjectResourcesExtension {
                async computeTotal() {
                    return this.getFiles().length + PreloadModelsExtension.PHASER_DEFS.length;
                }
                getFiles() {
                    return colibri.ui.ide.FileUtils.getAllFiles()
                        .filter(file => file.getExtension() === "js" || file.getExtension() === "ts")
                        .filter(file => file.getNameWithoutExtension() !== "phaser"
                        && file.getNameWithoutExtension() !== "phaser.min");
                }
                async preload(monitor) {
                    monaco.editor.getModels().forEach(model => model.dispose());
                    const utils = colibri.ui.ide.FileUtils;
                    const files = this.getFiles();
                    for (const file of files) {
                        const content = await utils.preloadAndGetFileString(file);
                        if (typeof content === "string") {
                            monaco.editor.createModel(content, "javascript", code.CodePlugin.fileUri(file.getFullName()));
                        }
                        monitor.step();
                    }
                    // preload phaser defs
                    for (const path of PreloadModelsExtension.PHASER_DEFS) {
                        const content = await code.CodePlugin.getInstance().getString(path);
                        monaco.editor.createModel(content, "javascript", code.CodePlugin.fileUri(path));
                        monitor.step();
                    }
                }
            }
            PreloadModelsExtension.PHASER_DEFS = ["data/matter.d.ts", "data/phaser.d.ts", "phaser-fixes.d.ts"];
            ui.PreloadModelsExtension = PreloadModelsExtension;
        })(ui = code.ui || (code.ui = {}));
    })(code = phasereditor2d.code || (phasereditor2d.code = {}));
})(phasereditor2d || (phasereditor2d = {}));
var phasereditor2d;
(function (phasereditor2d) {
    var code;
    (function (code) {
        var ui;
        (function (ui) {
            var editors;
            (function (editors) {
                class MonacoEditor extends colibri.ui.ide.FileEditor {
                    constructor(id, language, editorFactory) {
                        super(id, editorFactory);
                        this.addClass("MonacoEditor");
                        this._language = language;
                        this._outlineProvider = new editors.outline.MonacoEditorOutlineProvider(this);
                    }
                    getMonacoEditor() {
                        return this._editor;
                    }
                    getModel() {
                        return this._model;
                    }
                    onPartClosed() {
                        if (super.onPartClosed()) {
                            if (this._model) {
                                this.disposeModel();
                            }
                            if (this._editor) {
                                this._editor.dispose();
                            }
                            return true;
                        }
                        return false;
                    }
                    onPartActivated() {
                        setTimeout(() => {
                            this._editor.focus();
                        }, 10);
                    }
                    disposeModel() {
                        this.removeModelListeners();
                        this._model.dispose();
                        this._model = null;
                    }
                    createPart() {
                        const container = document.createElement("div");
                        container.classList.add("MonacoEditorContainer");
                        this._editor = monaco.editor.create(container, {
                            scrollBeyondLastLine: true,
                            fontSize: 16
                        });
                        // tslint:disable-next-line:no-bitwise
                        this._editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KEY_P, () => {
                            const manager = colibri.Platform.getWorkbench().getCommandManager();
                            manager.executeCommand(phasereditor2d.files.ui.actions.CMD_GO_TO_FILE);
                        });
                        this.getElement().appendChild(container);
                        this.updateContent();
                    }
                    getTokenAt(pos) {
                        const tokens = this.getTokensAt(pos);
                        return tokens.find(t => pos.column >= t.start && pos.column <= t.end);
                    }
                    getTokensAt(pos) {
                        const model = this._model;
                        const line = model.getLineContent(pos.lineNumber);
                        const result = monaco.editor.tokenize(line, this._language);
                        if (result.length > 0) {
                            const tokens = result[0];
                            const tokens2 = [];
                            let lastOffset = -1;
                            let lastType = null;
                            for (const token of tokens) {
                                if (lastType) {
                                    tokens2.push({
                                        type: lastType,
                                        value: line.substring(lastOffset, token.offset),
                                        start: lastOffset,
                                        end: token.offset
                                    });
                                }
                                lastType = token.type;
                                lastOffset = token.offset;
                            }
                            if (lastType) {
                                tokens2.push({
                                    type: lastType,
                                    value: line.substring(lastOffset),
                                    start: lastOffset,
                                    end: line.length
                                });
                            }
                            return tokens2;
                        }
                        return [];
                    }
                    async doSave() {
                        const content = this._model.getValue();
                        try {
                            await colibri.ui.ide.FileUtils.setFileString_async(this.getInput(), content);
                            this.setDirty(false);
                            this.refreshOutline();
                        }
                        catch (e) {
                            console.error(e);
                        }
                    }
                    async updateContent() {
                        const file = this.getInput();
                        if (!file) {
                            return;
                        }
                        if (!this._editor) {
                            return;
                        }
                        this._model = await this.createModel(file);
                        this._editor.setModel(this._model);
                        this.registerModelListeners(this._model);
                        this.setDirty(false);
                        this.refreshOutline();
                    }
                    async createModel(file) {
                        const content = await colibri.ui.ide.FileUtils.preloadAndGetFileString(file);
                        const model = monaco.editor.createModel(content, this._language);
                        return model;
                    }
                    registerModelListeners(model) {
                        // dirty
                        if (this._onDidChangeContentEvent) {
                            this._onDidChangeContentEvent.dispose();
                        }
                        this._onDidChangeContentEvent = this._model.onDidChangeContent(async (e) => {
                            const content = await colibri.ui.ide.FileUtils.getFileString(this.getInput());
                            this.setDirty(content !== this._model.getValue());
                        });
                        if (this.isInEditorArea()) {
                            // refresh outline
                            if (this._onDidChangeCountEvent) {
                                this._onDidChangeCountEvent.dispose();
                            }
                            this._modelLines = model.getLineCount();
                            this._onDidChangeCountEvent = model.onDidChangeContent(e => {
                                const count = model.getLineCount();
                                if (count !== this._modelLines) {
                                    this.refreshOutline();
                                    this._modelLines = count;
                                }
                            });
                            // reveal in outline
                            this._editor.onDidChangeCursorPosition(e => {
                                const offset = this._model.getOffsetAt(e.position);
                                this._outlineProvider.revealOffset(offset);
                            });
                        }
                    }
                    removeModelListeners() {
                        if (this._onDidChangeContentEvent) {
                            this._onDidChangeContentEvent.dispose();
                        }
                        if (this._onDidChangeCountEvent) {
                            this._onDidChangeCountEvent.dispose();
                        }
                    }
                    getEditorViewerProvider(key) {
                        switch (key) {
                            case phasereditor2d.outline.ui.views.OutlineView.EDITOR_VIEWER_PROVIDER_KEY:
                                if (this.isInEditorArea()) {
                                    return this._outlineProvider;
                                }
                                break;
                        }
                        return null;
                    }
                    async refreshOutline() {
                        if (this.isInEditorArea()) {
                            await this._outlineProvider.refresh();
                        }
                    }
                    layout() {
                        super.layout();
                        if (this._editor) {
                            this._editor.layout();
                        }
                    }
                    async onEditorInputContentChangedByExternalEditor() {
                        if (ui.ModelManager.handleFileName(this.getInput().getName())) {
                            // do nothing, the model manager will handle this!
                            return;
                        }
                        const model = this.getModel();
                        if (model) {
                            const str = await colibri.ui.ide.FileUtils.preloadAndGetFileString(this.getInput());
                            model.setValue(str);
                        }
                    }
                }
                editors.MonacoEditor = MonacoEditor;
            })(editors = ui.editors || (ui.editors = {}));
        })(ui = code.ui || (code.ui = {}));
    })(code = phasereditor2d.code || (phasereditor2d.code = {}));
})(phasereditor2d || (phasereditor2d = {}));
/// <reference path="./MonacoEditor.ts" />
var phasereditor2d;
(function (phasereditor2d) {
    var code;
    (function (code) {
        var ui;
        (function (ui) {
            var editors;
            (function (editors) {
                class CSSEditor extends editors.MonacoEditor {
                    constructor() {
                        super("phasereditor2d.core.ui.editors.CSSEditor", "css", CSSEditor.getFactory());
                    }
                    static getFactory() {
                        return this._factory
                            || (this._factory = new colibri.ui.ide.ContentTypeEditorFactory("CSS Editor", phasereditor2d.webContentTypes.core.CONTENT_TYPE_CSS, () => new CSSEditor()));
                    }
                    async requestOutlineItems() {
                        return [];
                    }
                }
                editors.CSSEditor = CSSEditor;
            })(editors = ui.editors || (ui.editors = {}));
        })(ui = code.ui || (code.ui = {}));
    })(code = phasereditor2d.code || (phasereditor2d.code = {}));
})(phasereditor2d || (phasereditor2d = {}));
/// <reference path="./MonacoEditor.ts" />
var phasereditor2d;
(function (phasereditor2d) {
    var code;
    (function (code) {
        var ui;
        (function (ui) {
            var editors;
            (function (editors) {
                class HTMLEditor extends editors.MonacoEditor {
                    constructor() {
                        super("phasereditor2d.core.ui.editors.HTMLEditor", "html", HTMLEditor.getFactory());
                    }
                    static getFactory() {
                        return this._factory
                            || (this._factory = new colibri.ui.ide.ContentTypeEditorFactory("HTML Editor", phasereditor2d.webContentTypes.core.CONTENT_TYPE_HTML, () => new HTMLEditor()));
                    }
                    async requestOutlineItems() {
                        return [];
                    }
                }
                editors.HTMLEditor = HTMLEditor;
            })(editors = ui.editors || (ui.editors = {}));
        })(ui = code.ui || (code.ui = {}));
    })(code = phasereditor2d.code || (phasereditor2d.code = {}));
})(phasereditor2d || (phasereditor2d = {}));
/// <reference path="./MonacoEditor.ts" />
var phasereditor2d;
(function (phasereditor2d) {
    var code;
    (function (code) {
        var ui;
        (function (ui) {
            var editors;
            (function (editors) {
                class JSONEditor extends editors.MonacoEditor {
                    constructor() {
                        super("phasereditor2d.core.ui.editors.JSONEditor", "json", JSONEditor.getFactory());
                    }
                    static getFactory() {
                        return this._factory
                            || (this._factory = new colibri.ui.ide.ContentTypeEditorFactory("JSON Editor", phasereditor2d.webContentTypes.core.CONTENT_TYPE_JSON, () => new JSONEditor()));
                    }
                    async requestOutlineItems() {
                        return [];
                    }
                }
                editors.JSONEditor = JSONEditor;
            })(editors = ui.editors || (ui.editors = {}));
        })(ui = code.ui || (code.ui = {}));
    })(code = phasereditor2d.code || (phasereditor2d.code = {}));
})(phasereditor2d || (phasereditor2d = {}));
/// <reference path="./MonacoEditor.ts" />
var phasereditor2d;
(function (phasereditor2d) {
    var code;
    (function (code) {
        var ui;
        (function (ui) {
            var editors;
            (function (editors) {
                class JavaScriptEditor extends editors.MonacoEditor {
                    constructor(lang) {
                        super("phasereditor2d.core.ui.editors.JavaScriptEditor", lang, lang === "javascript" ? JavaScriptEditor.getJavaScriptFactory() : JavaScriptEditor.getTypeScriptFactory());
                        this._finder = new phasereditor2d.pack.core.PackFinder();
                    }
                    static getJavaScriptFactory() {
                        return this._jsFactory
                            || (this._jsFactory = new colibri.ui.ide.ContentTypeEditorFactory("JavaScript Editor", phasereditor2d.webContentTypes.core.CONTENT_TYPE_JAVASCRIPT, () => new JavaScriptEditor("javascript")));
                    }
                    static getTypeScriptFactory() {
                        return this._tsFactory
                            || (this._tsFactory = new colibri.ui.ide.ContentTypeEditorFactory("TypeScript Editor", phasereditor2d.webContentTypes.core.CONTENT_TYPE_TYPESCRIPT, () => new JavaScriptEditor("typescript")));
                    }
                    async createModel(file) {
                        let model;
                        const content = await colibri.ui.ide.FileUtils.preloadAndGetFileString(file);
                        const uri = code.CodePlugin.fileUri(file.getFullName());
                        model = monaco.editor.getModel(uri);
                        if (content !== model.getValue()) {
                            model.setValue(content);
                        }
                        this._finder.preload();
                        return model;
                    }
                    onPartActivated() {
                        super.onPartActivated();
                        this._finder.preload();
                    }
                    onEditorFileNameChanged() {
                        const uri = code.CodePlugin.fileUri(this.getInput().getFullName());
                        this._model = monaco.editor.getModel(uri);
                        const editor = this.getMonacoEditor();
                        const state = editor.saveViewState();
                        editor.setModel(this._model);
                        editor.restoreViewState(state);
                        this.registerModelListeners(this._model);
                    }
                    getEmbeddedEditorState() {
                        const editor = this.getMonacoEditor();
                        if (editor) {
                            return this.getMonacoEditor().saveViewState();
                        }
                        return null;
                    }
                    restoreEmbeddedEditorState(state) {
                        const editor = this.getMonacoEditor();
                        if (editor && state) {
                            editor.restoreViewState(state);
                        }
                    }
                    getPropertyProvider() {
                        if (this.isInEditorArea()) {
                            if (!this._propertyProvider) {
                                this._propertyProvider = new editors.properties.JavaScriptSectionProvider();
                            }
                        }
                        return this._propertyProvider;
                    }
                    registerModelListeners(model) {
                        super.registerModelListeners(model);
                        const editor = this.getMonacoEditor();
                        if (this.isInEditorArea()) {
                            editor.getDomNode().addEventListener("click", async (e) => {
                                const pos = editor.getPosition();
                                const docItem = await this.getDocItemAtPosition(pos);
                                if (docItem) {
                                    this.setSelection([docItem]);
                                    return;
                                }
                                const item = await this.getAssetItemAtPosition(pos);
                                if (item) {
                                    this.setSelection([item]);
                                    return;
                                }
                                this.setSelection([]);
                            });
                        }
                    }
                    async getAssetItemAtPosition(pos) {
                        const token = this.getTokenAt(pos);
                        if (!token || token.type !== "string.js") {
                            return null;
                        }
                        let str = token.value;
                        // remove the ' or " or ` chars
                        str = str.substring(1, str.length - 1);
                        const obj = this._finder.findPackItemOrFrameWithKey(str);
                        return obj;
                    }
                    async getDocItemAtPosition(pos) {
                        const worker = await code.CodePlugin.getInstance().getJavaScriptWorker();
                        const offs = this.getMonacoEditor().getModel().getOffsetAt(pos);
                        const info = await worker.getQuickInfoAtPosition(code.CodePlugin.fileUri(this.getInput()).toString(), offs);
                        if (info) {
                            return new editors.properties.DocumentationItem(info);
                        }
                    }
                    disposeModel() {
                        // the model is disposed by the ModelsManager.
                        // but we should update it with the file content if the editor is dirty
                        if (this.isDirty()) {
                            const content = colibri.ui.ide.FileUtils.getFileString(this.getInput());
                            const model = this.getMonacoEditor().getModel();
                            model.setValue(content);
                        }
                        this.removeModelListeners();
                    }
                    async requestOutlineItems() {
                        const model = this.getMonacoEditor().getModel();
                        if (model) {
                            const worker = await code.CodePlugin.getInstance().getJavaScriptWorker();
                            const items = await worker.getNavigationBarItems(model.uri.toString());
                            return items.filter(i => i.text !== "<global>");
                        }
                        return [];
                    }
                }
                editors.JavaScriptEditor = JavaScriptEditor;
            })(editors = ui.editors || (ui.editors = {}));
        })(ui = code.ui || (code.ui = {}));
    })(code = phasereditor2d.code || (phasereditor2d.code = {}));
})(phasereditor2d || (phasereditor2d = {}));
/// <reference path="./MonacoEditor.ts" />
var phasereditor2d;
(function (phasereditor2d) {
    var code;
    (function (code) {
        var ui;
        (function (ui) {
            var editors;
            (function (editors) {
                class TextEditor extends editors.MonacoEditor {
                    constructor() {
                        super("phasereditor2d.core.ui.editors.TextLEditor", "text", TextEditor.getFactory());
                    }
                    static getFactory() {
                        return this._factory
                            || (this._factory = new colibri.ui.ide.ContentTypeEditorFactory("Text Editor", phasereditor2d.webContentTypes.core.CONTENT_TYPE_TEXT, () => new TextEditor()));
                    }
                    async requestOutlineItems() {
                        return [];
                    }
                }
                editors.TextEditor = TextEditor;
            })(editors = ui.editors || (ui.editors = {}));
        })(ui = code.ui || (code.ui = {}));
    })(code = phasereditor2d.code || (phasereditor2d.code = {}));
})(phasereditor2d || (phasereditor2d = {}));
/// <reference path="./MonacoEditor.ts" />
var phasereditor2d;
(function (phasereditor2d) {
    var code;
    (function (code) {
        var ui;
        (function (ui) {
            var editors;
            (function (editors) {
                class XMLEditor extends editors.MonacoEditor {
                    constructor() {
                        super("phasereditor2d.core.ui.editors.XMLEditor", "xml", XMLEditor.getFactory());
                    }
                    static getFactory() {
                        return this._factory
                            || (this._factory = new colibri.ui.ide.ContentTypeEditorFactory("XML Editor", phasereditor2d.webContentTypes.core.CONTENT_TYPE_XML, () => new XMLEditor()));
                    }
                    async requestOutlineItems() {
                        return [];
                    }
                }
                editors.XMLEditor = XMLEditor;
            })(editors = ui.editors || (ui.editors = {}));
        })(ui = code.ui || (code.ui = {}));
    })(code = phasereditor2d.code || (phasereditor2d.code = {}));
})(phasereditor2d || (phasereditor2d = {}));
var phasereditor2d;
(function (phasereditor2d) {
    var code;
    (function (code) {
        var ui;
        (function (ui) {
            var editors;
            (function (editors) {
                var outline;
                (function (outline) {
                    var controls = colibri.ui.controls;
                    class MonacoEditorOutlineProvider extends colibri.ui.ide.EditorViewerProvider {
                        constructor(editor) {
                            super();
                            this._editor = editor;
                            this._items = [];
                            this._itemsMap = new Map();
                        }
                        setViewer(viewer) {
                            viewer.eventOpenItem.addListener(() => {
                                const obj = viewer.getSelectionFirstElement();
                                if (Array.isArray(obj.spans)) {
                                    const span = obj.spans[0];
                                    const editor = this._editor.getMonacoEditor();
                                    const model = this._editor.getMonacoEditor().getModel();
                                    const pos = model.getPositionAt(span.start);
                                    const end = model.getPositionAt(span.start + span.length);
                                    editor.setPosition(pos);
                                    editor.revealPosition(pos, monaco.editor.ScrollType.Immediate);
                                    const range = {
                                        endColumn: end.column,
                                        endLineNumber: end.lineNumber,
                                        startColumn: pos.column,
                                        startLineNumber: pos.lineNumber,
                                    };
                                    editor.setSelection(range);
                                    editor.focus();
                                }
                            });
                            super.setViewer(viewer);
                        }
                        prepareViewerState(state) {
                            state.selectedObjects = new Set([...state.selectedObjects]
                                .map(obj => this._itemsMap.get(obj.id) || obj));
                            state.expandedObjects = new Set([...state.expandedObjects]
                                .map(obj => this._itemsMap.get(obj.id) || obj));
                        }
                        getContentProvider() {
                            return new outline.MonacoOutlineContentProvider(this);
                        }
                        getLabelProvider() {
                            // tslint:disable-next-line:new-parens
                            return new class {
                                getLabel(obj) {
                                    return obj.text;
                                }
                            };
                        }
                        getCellRendererProvider() {
                            return new outline.MonacoOutlineCellRendererProvider();
                        }
                        getTreeViewerRenderer(viewer) {
                            return new controls.viewers.TreeViewerRenderer(viewer);
                        }
                        getPropertySectionProvider() {
                            return null;
                        }
                        getInput() {
                            return this._editor.getInput();
                        }
                        getItems() {
                            return this._items;
                        }
                        async preload() {
                            // nothing for now
                        }
                        revealOffset(offset) {
                            const item = this.findItemAtOffset(this._items, offset);
                            if (item) {
                                this.setSelection([item], true, false);
                            }
                        }
                        findItemAtOffset(items, offset) {
                            for (const item of items) {
                                if (Array.isArray(item.childItems)) {
                                    const found = this.findItemAtOffset(item.childItems, offset);
                                    if (found) {
                                        return found;
                                    }
                                }
                                const span = item.spans[0];
                                if (offset >= span.start && offset <= span.start + span.length) {
                                    return item;
                                }
                            }
                            return null;
                        }
                        async refresh() {
                            this._items = await this._editor.requestOutlineItems();
                            this._itemsMap = new Map();
                            this.buildItemsMap(this._items, "");
                            this.repaint();
                        }
                        buildItemsMap(items, prefix) {
                            for (const item of items) {
                                item.id = prefix + "#" + item.text + "#" + item.kind;
                                this._itemsMap.set(item.id, item);
                                if (Array.isArray(item.childItems)) {
                                    this.buildItemsMap(item.childItems, item.id);
                                    item.childItems.sort((a, b) => {
                                        return a.spans[0].start - b.spans[0].start;
                                    });
                                }
                            }
                        }
                        getUndoManager() {
                            return this._editor.getUndoManager();
                        }
                    }
                    outline.MonacoEditorOutlineProvider = MonacoEditorOutlineProvider;
                })(outline = editors.outline || (editors.outline = {}));
            })(editors = ui.editors || (ui.editors = {}));
        })(ui = code.ui || (code.ui = {}));
    })(code = phasereditor2d.code || (phasereditor2d.code = {}));
})(phasereditor2d || (phasereditor2d = {}));
var phasereditor2d;
(function (phasereditor2d) {
    var code;
    (function (code) {
        var ui;
        (function (ui) {
            var editors;
            (function (editors) {
                var outline;
                (function (outline) {
                    var controls = colibri.ui.controls;
                    class MonacoOutlineCellRendererProvider {
                        getCellRenderer(obj) {
                            let name;
                            if (typeof obj.kind === "string") {
                                name = MonacoOutlineCellRendererProvider.map[obj.kind];
                            }
                            if (!name) {
                                name = code.ICON_SYMBOL_VARIABLE;
                            }
                            const img = code.CodePlugin.getInstance().getIcon(name);
                            return new controls.viewers.IconImageCellRenderer(img);
                        }
                        preload(args) {
                            return controls.Controls.resolveNothingLoaded();
                        }
                    }
                    MonacoOutlineCellRendererProvider.map = {
                        class: code.ICON_SYMBOL_CLASS,
                        const: code.ICON_SYMBOL_CONSTANT,
                        field: code.ICON_SYMBOL_FIELD,
                        interface: code.ICON_SYMBOL_INTERFACE,
                        method: code.ICON_SYMBOL_METHOD,
                        function: code.ICON_SYMBOL_METHOD,
                        constructor: code.ICON_SYMBOL_METHOD,
                        namespace: code.ICON_SYMBOL_NAMESPACE,
                        property: code.ICON_SYMBOL_PROPERTY,
                        variable: code.ICON_SYMBOL_VARIABLE,
                    };
                    outline.MonacoOutlineCellRendererProvider = MonacoOutlineCellRendererProvider;
                })(outline = editors.outline || (editors.outline = {}));
            })(editors = ui.editors || (ui.editors = {}));
        })(ui = code.ui || (code.ui = {}));
    })(code = phasereditor2d.code || (phasereditor2d.code = {}));
})(phasereditor2d || (phasereditor2d = {}));
var phasereditor2d;
(function (phasereditor2d) {
    var code;
    (function (code) {
        var ui;
        (function (ui) {
            var editors;
            (function (editors) {
                var outline;
                (function (outline) {
                    class MonacoOutlineContentProvider {
                        constructor(provider) {
                            this._provider = provider;
                        }
                        getRoots(input) {
                            return this._provider.getItems();
                        }
                        getChildren(parent) {
                            if (parent.childItems) {
                                return parent.childItems;
                            }
                            return [];
                        }
                    }
                    outline.MonacoOutlineContentProvider = MonacoOutlineContentProvider;
                })(outline = editors.outline || (editors.outline = {}));
            })(editors = ui.editors || (ui.editors = {}));
        })(ui = code.ui || (code.ui = {}));
    })(code = phasereditor2d.code || (phasereditor2d.code = {}));
})(phasereditor2d || (phasereditor2d = {}));
var phasereditor2d;
(function (phasereditor2d) {
    var code;
    (function (code) {
        var ui;
        (function (ui) {
            var editors;
            (function (editors) {
                var properties;
                (function (properties) {
                    class DocumentationItem {
                        constructor(data) {
                            this._data = data;
                            this._converter = new window["showdown"].Converter();
                        }
                        getData() {
                            return this._data;
                        }
                        toHTML() {
                            let html = "";
                            if (this._data.displayParts) {
                                const line = this._data.displayParts.map(p => {
                                    if (p.kind === "methodName" || p.kind === "parameterName" || p.kind === "className") {
                                        return `<b>${p.text}</b>`;
                                    }
                                    return p.text;
                                }).join("");
                                html += `<code>${line}</code><br>`;
                            }
                            if (this._data.documentation) {
                                const docs = this._data.documentation.map(doc => doc.text).join("\n");
                                html += this._converter.makeHtml(docs);
                            }
                            if (this._data.tags) {
                                const tags = this._data.tags
                                    .map(t => "<p><b><code>@" + t.name + "</code></b> " + t.text + "</p>").join("");
                                html += tags;
                            }
                            return html;
                        }
                    }
                    properties.DocumentationItem = DocumentationItem;
                })(properties = editors.properties || (editors.properties = {}));
            })(editors = ui.editors || (ui.editors = {}));
        })(ui = code.ui || (code.ui = {}));
    })(code = phasereditor2d.code || (phasereditor2d.code = {}));
})(phasereditor2d || (phasereditor2d = {}));
var phasereditor2d;
(function (phasereditor2d) {
    var code;
    (function (code) {
        var ui;
        (function (ui) {
            var editors;
            (function (editors) {
                var properties;
                (function (properties) {
                    var controls = colibri.ui.controls;
                    class DocumentationSection extends controls.properties.PropertySection {
                        constructor(page) {
                            super(page, "phasereditor2d.code.ui.editors.properties.DocumentationSection", "Documentation", true, false);
                        }
                        createForm(parent) {
                            const comp = this.createGridElement(parent, 1);
                            comp.style.alignItems = "self-start";
                            const docElement = document.createElement("div");
                            docElement.style.height = "100%";
                            docElement.classList.add("UserSelectText");
                            comp.appendChild(docElement);
                            this.addUpdater(() => {
                                const item = this.getSelectionFirstElement();
                                docElement.innerHTML = item.toHTML();
                            });
                        }
                        canEdit(obj, n) {
                            return obj instanceof properties.DocumentationItem;
                        }
                        canEditNumber(n) {
                            return n === 1;
                        }
                    }
                    properties.DocumentationSection = DocumentationSection;
                })(properties = editors.properties || (editors.properties = {}));
            })(editors = ui.editors || (ui.editors = {}));
        })(ui = code.ui || (code.ui = {}));
    })(code = phasereditor2d.code || (phasereditor2d.code = {}));
})(phasereditor2d || (phasereditor2d = {}));
var phasereditor2d;
(function (phasereditor2d) {
    var code;
    (function (code) {
        var ui;
        (function (ui) {
            var editors;
            (function (editors) {
                var properties;
                (function (properties) {
                    var controls = colibri.ui.controls;
                    class JavaScriptSectionProvider extends controls.properties.PropertySectionProvider {
                        addSections(page, sections) {
                            sections.push(new properties.DocumentationSection(page));
                            new phasereditor2d.pack.ui.properties.AssetPackPreviewPropertyProvider()
                                .addSections(page, sections);
                        }
                    }
                    properties.JavaScriptSectionProvider = JavaScriptSectionProvider;
                })(properties = editors.properties || (editors.properties = {}));
            })(editors = ui.editors || (ui.editors = {}));
        })(ui = code.ui || (code.ui = {}));
    })(code = phasereditor2d.code || (phasereditor2d.code = {}));
})(phasereditor2d || (phasereditor2d = {}));
