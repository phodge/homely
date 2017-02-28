au! BufReadPost,BufNewFile docs/* call <SID>InitDocsFolder()
au! BufReadPost,BufNewFile docs/slides.rst nnoremap <buffer> <space>p :!./makeslides.sh<CR>

fun! <SID>InitDocsFolder()
  nnoremap <buffer> <space>d :!cd docs && make html<CR>
endfun
