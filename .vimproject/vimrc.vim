au! BufReadPost,BufNewFile docs/* call <SID>InitDocsFolder()

fun! <SID>InitDocsFolder()
  nnoremap <buffer> <space>d :!cd docs && make html<CR>
endfun
