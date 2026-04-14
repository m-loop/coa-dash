#!/usr/bin/env node
/**
 * Standalone Feishu WS test using @larksuiteoapi/node-sdk (same as openclaw-lark).
 * Uses nanobot app credentials.
 */
import { Client, WSClient, EventDispatcher, LoggerLevel } from '@larksuiteoapi/node-sdk';

const APP_ID = 'cli_a924482b98785bc8';
const APP_SECRET = 'fXZuYFH4SDIypr0dBVc5Xg0Mvqu1xq1l';

console.log('[TEST] Creating EventDispatcher...');
const dispatcher = new EventDispatcher({
    encryptKey: '',
    verificationToken: '',
});

dispatcher.register({
    'im.message.receive_v1': async (data) => {
        console.log('[EVENT] im.message.receive_v1 received!');
        console.log('[EVENT] data:', JSON.stringify(data).substring(0, 500));
    },
});

console.log('[TEST] Creating WSClient...');
const wsClient = new WSClient({
    appId: APP_ID,
    appSecret: APP_SECRET,
    domain: 'https://open.feishu.cn',
    loggerLevel: LoggerLevel.info,
});

console.log('[TEST] Starting WS connection (nanobot app)...');
console.log('[TEST] Send a message to the bot now!');

await wsClient.start({
    eventDispatcher: dispatcher,
});
