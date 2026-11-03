import test from 'node:test';
import assert from 'node:assert/strict';
import {resolveTheme} from './theme.js';

test('saved theme wins over the system preference',()=>{
  assert.equal(resolveTheme('light',true),'light');
  assert.equal(resolveTheme('dark',false),'dark');
});

test('system preference is used until a theme is saved',()=>{
  assert.equal(resolveTheme(null,true),'dark');
  assert.equal(resolveTheme(null,false),'light');
});
