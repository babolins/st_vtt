import { mount } from 'svelte';
// Body face of the paper theme (see app.css). Declaring a face costs nothing:
// a browser fetches one only when rendered text actually asks for it.
import '@fontsource/libre-caslon-text/400.css';
import '@fontsource/libre-caslon-text/400-italic.css';
import '@fontsource/libre-caslon-text/700.css';
import './app.css';
import App from './App.svelte';
import { installLinkResolver } from './lib/links.svelte';

// [[Cerys]] in any text field becomes a link to whoever that is.
installLinkResolver();

mount(App, { target: document.getElementById('app')! });
