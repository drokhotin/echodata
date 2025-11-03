def translit(s, to='rueng'):
    translations ={
        'rueng':{'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'E', 'Ж': 'ZH', 
                 'З': 'Z', 'И': 'I', 'Й': 'J', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N', 'О': 'O', 
                  'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U', 'Ф': 'F', 'Х': 'H', 'Ц': 'C', 
                  'Ч': 'CH', 'Ь': "'", 'Ъ': "'", 'Ы': 'Y', 'Э': 'E', 'Ю': 'YU', 'Я': 'YA', 'а': 'a', 
                  'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh', 'з': 'z', 
                  'и': 'i', 'й': 'j', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 
                  'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'ch', 'ь': "'", 
                  'ъ': "'", 'ы': 'y', 'э': 'e', 'ю': 'yu', 'я': 'ya'},
        'engru':{'a': 'а', 'b': 'б', 'c': 'ц', 'd': 'д', 'e': 'е', 'f': 'ф', 'g': 'г', 'h': 'х', 'i': 'и', 
                 'j': 'й', 'k': 'к', 
                 'l': 'л', 'm': 'м', 'n': 'н', 'o': 'о', 'p': 'п', 'q': 'q', 'r': 'р', 's': 'с', 't': 'т', 
                 'u': 'у', 'v': 'в', 'w': 'w', 'x': 'x', 'y': 'ы', 'z': 'з', 'A': 'А', 'B': 'Б', 'C': 'Ц', 
                 'D': 'Д', 'E': 'Е', 'F': 'Ф', 'G': 'Г', 'H': 'Х', 'I': 'И', 'J': 'Й', 'K': 'К', 'L': 'Л', 
                 'M': 'М', 'N': 'Н', 'O': 'О', 'P': 'П', 'Q': 'Q', 'R': 'Р', 'S': 'С', 'T': 'Т', 'U': 'У', 
                 'V': 'В', 'W': 'W', 
                 'X': 'X', 'Y': 'Ы', 'Z': 'З'}}
    return s.translate(''.maketrans(translations[to]))


def signletter(fiolat='Familija Imya Otchestvo'):
    ns=' '
    s=fiolat.replace('ph', 'f')
    s=s.replace('?', '\?')
    s=s.replace('k', '[кх]')
    s=s.replace('x', 'ks')
    s=s.replace('i', '[ьыий]')
    s=s.replace('ts', '(ц|тс)')
    s=s.replace('u', '[ую]')
    s=s.replace('o', '[оеё]')
    s=s.replace('e', '[эеё]')
    s=s.replace('s', '[сцщчш]')
    s=s.replace('a', '[ая]')
    s=s.replace('z', '[зж]')
    for c in s:
        if c in 'gbdflmnrvfptu ' or c not in "abcdefghijklmnopqrstuvwxyz`''":
            ns+=c
        if c in  'abcdefghijklmnopqrstuvwxyz' and ns[-1]!='%':
            ns+='%'
    ns=ns[1:].replace('%%', '%').replace('%', '.*')
    ns='^'+ns.replace(' ', ' ^')
    ns=translit(ns, 'engru')
    return(ns)



#path_to_echodata='http://localhost:5000' # development
path_to_echodata='http://192.168.31.100:8080' #hospital

#path_to_echoview='http://localhost:5001'
path_to_echoview='http://192.168.31.100:8081' #hospital

echoview_username='echoview@echoview.echoview'
echoview_password='EcHoViEw'
