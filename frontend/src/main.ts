import { mount } from 'svelte';
import './app.css';
import App from './App.svelte';
import { installLinkResolver } from './lib/links.svelte';

// [[Cerys]] in any text field becomes a link to whoever that is.
installLinkResolver();

mount(App, { target: document.getElementById('app')! });
