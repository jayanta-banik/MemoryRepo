import * as assert from 'node:assert/strict';
import * as vscode from 'vscode';

import { helloMessage } from '../extension';

suite('MemoryRepo extension', () => {
  test('builds a hello message for a repo name', () => {
    assert.equal(helloMessage('ExampleRepo'), 'Hello from ExampleRepo');
  });

  test('contributes the hello command', async () => {
    const commands = await vscode.commands.getCommands(true);

    assert.ok(commands.includes('memoryrepo.hello'));
  });
});
