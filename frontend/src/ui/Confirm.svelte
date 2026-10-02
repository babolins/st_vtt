<script lang="ts">
  import Modal from './Modal.svelte';
  let {
    title = 'Are you sure?',
    text = '',
    onyes,
    onclose,
    danger = true,
  }: { title?: string; text?: string; onyes: () => void; onclose: () => void; danger?: boolean } = $props();
</script>

<Modal {title} {onclose}>
  {#if text}<p>{text}</p>{/if}
  <div class="row" style="justify-content:flex-end">
    <button onclick={onclose}>Cancel</button>
    <button
      class={danger ? 'danger' : 'primary'}
      onclick={() => {
        onyes();
        onclose();
      }}>Yes</button
    >
  </div>
</Modal>
