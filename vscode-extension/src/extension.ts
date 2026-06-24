import * as vscode from 'vscode';

export function getWorkspaceRepoName(): string {
  return vscode.workspace.workspaceFolders?.[0]?.name ?? 'MemoryRepo';
}

export function helloMessage(repoName = getWorkspaceRepoName()): string {
  return `Hello from ${repoName}`;
}

export function activate(context: vscode.ExtensionContext): void {
  const disposable = vscode.commands.registerCommand('memoryrepo.hello', () => {
    void vscode.window.showInformationMessage(helloMessage());
  });

  context.subscriptions.push(disposable);
}

export function deactivate(): void {}
