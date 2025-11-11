import re
import html
import bleach
import pandas as pd

locale='ru'
types_of_coded_fields = ['numeric', 'textarea', 'rte', 'text', 'select_one', 'other_starts_with',
                             'others_others', 'rich_sentence', 'sentence']
funcs = ['SIN', 'COS', 'LOG', 'MAX', 'MIN', 'LOG', 'ABS', 'TRUNC']


def form_from_xlsx(file_path, title, header, description):
    df = pd.read_excel(file_path, engine='openpyxl')
    df = df.fillna('')
    df['code'] = df['code'].str.upper()
    df['calc'] = df['calc'].str.upper()
    df['logic'] = df['logic'].str.upper()
    df['textarea'] = df['textarea'].str.upper() 

    check = check_syntax(df)
    printable=''
    html=''

    if check=='ok':
        printable = print_total(title, header, description, 
                                scripts="", 
                                parameters=html_printable_contents(df))
    
        html= html_total(title, header, description, 
                         scripts=html_form_scripts(df), 
                         parameters=html_form_contents(df))
  
    return({'printable': printable, 'html': html, 'check':check})
 


def extract_codes(formula):
    import re
    pattern = r'(?<![\'"])(?<!\w)[A-Za-z_][A-Za-z0-9_]*'
    return [arg for arg in list(set(re.findall(pattern, formula))) if arg not in funcs]

def num(n):
    try:
        return(float(n))
    except:
        return('NaN')


def safe(inp):
    return(html.escape(str(inp)))

def clean(user_html):
    clean_html = bleach.clean(
        user_html,
        tags=["b", "i", "u", "p", "ul", "ol", "li", "a", "br"],
        attributes={"a": ["href", "title"]},
        strip=True
        )
    return(clean_html)

def check_syntax(df):
    codes=['_AGE', '_GENDER', '_TITLE']
    calcs=[]
    logics=[]

    for index, row in df.iterrows():
        if row.code!='':
            if extract_codes(row.code)[0]==row.code: codes.append(row.code)
            else: return(f"Incorrect code [{row.code}] in line {index}!")
                
    for index, row in df.iterrows():
        if row.code=='' and row.type in types_of_coded_fields:
            return(f"No code name in line {index} with type {row.type}.")
        if row.code!='' and row.type not in types_of_coded_fields:
            return(f"Incorrect type [{type}] for code [{row.code}] in line {index}.")
        if row.logic!='':
            for code in extract_codes(row.logic):
                if code not in codes: return(f"Logic [{row.logic}] contains code [{code}] not in codes in linde {index}!")
        if row.calc!='':
            for code in extract_codes(row.calc):
                if code not in codes: return(f"Calculation [{row.calc}] contains code [{code}] not in codes in line {index}!")
    return('ok')
            
            
    

def html_form_contents(df):
    parameters = []
    nl='\n'

    tab=0
    sentence_group=0
    tabs=[]
    codes = []
    other_starts = []
    column=0

    for index, row in df.iterrows():
        codes.append(str(row.code))
        codes=list(set(codes))
        codes.remove('') if '' in codes else None
        if row.type=='other_starts_with':
            other_starts.append(row.code)


    for index, row in df.iterrows():
        if row.code!='':
            if row.type=='numeric':
                reference, lower, upper = row.reference, row.lower, row.upper
                if reference == '':
                    if lower == '' and upper!='': reference = f"< {upper}"
                    elif lower != '' and upper=='': reference = f"> {lower}"
                    elif lower!='' and upper!='': reference = f"{lower}—{upper}"
                        
                parameters.append(f"""
        <div class="w3-row-padding w3-col-bottom w3-border-bottom" id='row_{safe(row.code)}'>
            <input type='hidden' id='hide_{safe(row.code)}' name='hide_{safe(row.code)}' value='{{{{ echo.hide_{safe(row.code)} }}}}'>        
            <div class="w3-col s7">
              <label for='{safe(row.code)}'>
                {safe(row.parameter)}{(lambda x: "" if x == "" else ", " + x)(safe(row.get('units', '')))}
              </label>
            </div>
            <div class="w3-col s3 w3-small w3-center w3-text-grey">
                {safe(reference)}
                <span id='ref_{safe(row.code)}'></span>
                <input hidden name='ref_{safe(row.code)}' id='inp_{safe(row.code)}' value=''>
            </div>

            <div class="w3-col s2">
              <input type='number' step='{safe(row.get('precision', 1))}' name='{safe(row.code)}' id='{safe(row.code)}' value='{{{{ echo.{safe(row.code)} }}}}' class="w3-input w3-round">
            </div>
        </div>""")
        
            if row.type=='text':
                parameters.append(f"""
        <div class="w3-row-padding w3-col-bottom w3-border-bottom" id='row_{safe(row.code)}'>
            <input type='hidden' id='hide_{safe(row.code)}' name='hide_{safe(row.code)}' value='{{{{ echo.hide_{safe(row.code)} }}}}'>        
            <div class="w3-col s7">
               <label for='{safe(row.code)}'>{safe(row.parameter)}</label>
            </div>
            <div class="w3-col s5">
            
            <input type='text' name='{safe(row.code)}' id='{safe(row.code)}' value='{{{{ echo.{safe(row.code)} }}}}' class="w3-input w3-round">
            </div>

        </div>""")
            
            if row.type=='select_one':
                parameters.append(f"""
        <div class="w3-row-padding w3-col-bottom w3-border-bottom" id='row_{safe(row.code)}'>
            <input type='hidden' id='hide_{safe(row.code)}' name='hide_{safe(row.code)}' value='{{{{ echo.hide_{safe(row.code)} }}}}'>        
            <div class="w3-col s7">
                <label for = '{safe(row.code)}'>{safe(row.parameter)}</label>
            </div>
            <div class="w3-col s5">
               <select name='{safe(row.code)}' id='{safe(row.code)}' class="w3-input w3-round w3-small">""")
                option=0
                for choice in [option.split(' | ') for option in row.choices.split(' / ')]:
                    option+=1
                    parameters.append(f"""
                    <option value='{choice[0]}' 
                    {{{{  'selected' if ('{choice[0]}'== echo.{safe(row.code)} or 
                    (''==echo.{safe(row.code)} and {option}==1)) else '' }}}} 
                    class='w3-select w3-border'>{choice[1]}</option>""")

                parameters.append(f"""
               </select>
            </div>
        </div>""")

            if row.type == 'textarea':
                parameters.append(f"""
        <div class="w3-row-padding" id='row_{safe(row.code)}'>
            <input type='hidden' id='hide_{safe(row.code)}' name='hide_{safe(row.code)}' value='{{{{ echo.hide_{safe(row.code)} }}}}'>
            <div class="w3-col s12">{safe(row.parameter)}</div>
        </div>
        <div class="w3-row-padding">
            <div class="w3-col s12">
            <textarea name='{safe(row.code)}' id='{safe(row.code)}' placeholder="Описательная часть (добавляйте предложения внизу)">{{{{ echo.{safe(row.code)} }}}}</textarea>
            </div>

        </div>""")

            if row.type == 'rte':
                parameters.append(f"""
        <div class="w3-row-padding" id='row_{safe(row.code)}'>
            <input type='hidden' id='hide_{safe(row.code)}' name='hide_{safe(row.code)}' value='{{{{ echo.hide_{safe(row.code)} }}}}'>
            <div class="w3-col s12">{safe(row.parameter)}</div>
        </div>
        <div class="w3-row-padding">
            <div class="w3-col s12">

            <div class="rte" data-name="{safe(row.code)}">{{{{ echo.{safe(row.code)} | safe }}}}</div>
            </div>

        </div>""")

            
            if row.type == 'sentence':
                parameters.append(f"""
        <div class="w3-row-padding" id='row_{safe(row.code)}'>
            <input type='hidden' id='hide_{safe(row.code)}' name='hide_{safe(row.code)}' value='{{{{ echo.hide_{safe(row.code)} }}}}'>        
            <div class="w3-col s12 text-area-sentence" onclick="document.getElementById('{safe(row.textarea)}').value+=
            document.getElementById('{safe(row.code)}').innerHTML+'\\n';">
            +
            <label id='{safe(row.code)}'>{safe(row.parameter)}</label>
            </div>
        </div>""")

            if row.type == 'rich_sentence':
                parameters.append(f"""
        <div class="w3-row-padding" id='row_{safe(row.code)}'>
            <input type='hidden' id='hide_{safe(row.code)}' name='hide_{safe(row.code)}' value='{{{{ echo.hide_{safe(row.code)} }}}}'>        
            <div class="w3-col s12 text-area-sentence" onclick="appendRTE('{safe(row.textarea)}', '{safe(row.code)}')">
            + 
            <label id='{safe(row.code)}'>{clean(row.parameter)}</label>
            </div>
        </div>""")


        if row.type == 'begin_column1':
            column=1
            parameters.append("""
        <div class="w3-col s6 column-overflow">""")
        if row.type == 'begin_column2':
            column=2
            parameters.append("""
        </div><div class="w3-col s6 column-overflow">""")

        
        
        if row.type=='begin_tab':
            tab+=1
            parameters.append(f"""
   		<div id="tab{tab}" class="w3-container w3-border tab-content" {'style="display:block"' if tab==1 else ''}>
            <div class="w3-row-padding">
        """)
            tabs.append(f"""
            <div class="w3-bar-item w3-button tablink" onclick="openTab(event, 'tab{tab}')">{safe(row.parameter)}</div>""")
                              
        if row.type=='end_columns':
            column=0
            parameters.append("""
                </div>endcol""")

        if row.type=='end_tab':
            if column:
                parameters.append("""
                </div>""")
                column=0
            parameters.append(f"""
            </div>
        </div>
        """)

        if row.type=='begin_sentence_group':
            sentence_group+=1
            parameters.append(f"""
        <div class="w3-row-padding">
            <div class="text-area-sentence" style = "color: blue; font-weight: bold;" onclick="showhide('sentence-group-{sentence_group}')">
            <label><span id="sentence-group-{sentence_group}-sign">&#9205;</span> {safe(row.parameter)}</label>
            </div>
        </div>
         <div id="sentence-group-{sentence_group}" class="sentence-group" style="border-left-style: solid;border-left-color:blue;padding-left:1em;display:none;">
        """)
  
        if row.type=='end_sentence_group':
            parameters.append(f"""
   		    </div>
        """)


        if row.type=='other_starts_with':

            parameters.append(f"""
        <div class="w3-row-padding" id='row_{safe(row.code)}others'>
            <input type='hidden' id='hide_{safe(row.code)}others' name='hide_{safe(row.code)}others' 
             value='{{{{ echo.hide_{safe(row.code)}others }}}}'>
            <div class="w3-col s12">{safe(row.parameter)}</div>
        </div>
        <div class="w3-row-padding">
            <div class="w3-col s12">
               <div class="rte" data-name="{safe(row.code)}others">
                {{% if echo.get('{safe(row.code)}others', 'None')=='None' %}}
                  {{% for key, parameter in echo.items() if key.startswith('{row.code}') and key not in {[code for code in codes if code.startswith(safe(row.code))]} %}}
                    {{{{ key | translate }}}}: {{{{ parameter | translate }}}} <br>
                  {{% endfor %}}
                {{% else %}}
                  {{{{ echo.{safe(row.code)}others | safe }}}}
                {{% endif %}}
               </div>

            </div>

        </div>""")


            


        
        
        if row.type=='other_other':
            codes_not_starting_with = codes.copy()
            for start in other_starts:
                for code in codes:
                    if code.startswith(start):
                        codes_not_starting_with.remove(code)

            parameters.append(f"""
        {{% for key, parameter in echo.items() if not ({' or '.join([f"key.startswith('{code}')" for code in other_starts])}) 
        and key not in {codes_not_starting_with} %}}
        <div class="w3-row-padding" id='row_{{{{ key }}}}'>
            <div class="w3-col s8">{{{{ parameter.name | translate }}}}, {{{{ parameter.units | translate }}}}</div>
            <div class="w3-col s2
            <input  type='number' name='{{{{ key }}}}' id='{{{{ key }}}}' value='{{{{ parameter.value }}}}' class="w3-input w3-border">
            </div>
            
        </div>
        {{% endfor %}}
        """)

            


    tabs='\n'.join(tabs)	     
    parameters = '\n'.join(parameters)

    if tabs!='':
        parameters=f"""
    <div class="w3-bar w3-green">
    {tabs}
    </div>
    <div class="tab-overflow">
    {parameters}
    </div>
    """
    else:
        parameters=f"""
        <div class="tab-overflow">
        {parameters}
        </div>
        """
    return(parameters)




def html_printable_contents(df):
    parameters = []
    nl='\n'

    tab=0
    sentence_group=0
    tabs=[]
    codes = []
    other_starts = []
    column=0
    table=0
    elements=0

    for index, row in df.iterrows():
        codes.append(str(row.code))
        codes=list(set(codes))
        codes.remove('') if '' in codes else None
        if row.type=='other_starts_with':
            other_starts.append(row.code)

    parameters.append("{% set ns = namespace(counter=0) %}")
    for index, row in df.iterrows():
        
        if row.type == 'begin_column1':
            column=1
            if table==1: 
                table=0
                parameters.append("""
                {% if rows %}
                    <table>
                       {{ rows | join('\n') | safe }}
                    </table>
                {% endif %}
                {% set rows = [] %}""")
            parameters.append("""{% set tab_heading.heading = tab_heading.heading + '<div class="two-columns"><div class="column-left">' %}""")

        if row.type == 'begin_column2':
            if table==1: 
                table=0
                parameters.append("""
                {% if rows %}
                    <table>
                       {{ rows | join('\n') | safe }}
                    </table>
                {% endif %}
                {% set rows = [] %}""")
            if column==1:
                parameters.append(f"""
                {{% if not tab_heading.shown %}}
                  {{% set tab_heading.heading = tab_heading.heading + '</div>
        <div class="column-right">' %}}
                {{% else %}}
                   </div>
                   <div class="column-right">
                {{% endif %}}
                """)
                column=2
            

            
            
        if row.type=='begin_tab':
            column=0
            if table==1: 
                table=0
                parameters.append("""
                {% if rows %}
                    <table>
                       {{ rows | join('\n') | safe }}
                    </table>
                {% endif %}
                {% set rows = [] %}""")
 #           parameters.append(f"<h2>{safe(row.parameter)}</h2>")
            parameters.append(f"""{{% set tab_heading = namespace(heading = '<h2>{safe(row.parameter)}</h2>', heading_shown=false) %}}
             {{% set rows = [] %}}""")
            


        if row.type=='end_tab':
            if table==1: 
                parameters.append("""{% if rows %}
                <table> 
                   {{ rows | join('\n') | safe }}
                </table>
                {% endif %}
                {% set rows = [] %}""")
                table=0
            if column>0:
                parameters.append(f"""
                {{% if tab_heading.shown %}}
                  </div></div>
                {{% endif %}}""")
            
            column=0
        
        
        if row.type=='numeric':
            parameters.append(f"""
                {{% if echo.{safe(row.code)}!='' and echo.hide_{safe(row.code)}!="1" %}}
                
                {{% if not tab_heading.shown %}}
                  {{{{ tab_heading.heading | safe }}}}
                  {{% set tab_heading.shown = true %}}
                {{% endif %}}""")
            if table==0:
                table=1
            parameters.append(f"""
                {{% set block %}}
                <tr>
                   <td>{safe(row.parameter)}, {safe(row.get('units', ''))}</td>
                   <td>{{{{ echo.ref_{safe(row.code)} }}}}</td>
                   <td>{{{{ echo.{safe(row.code)} { "| string|replace('.', ',')" if locale=='ru' else ''} }}}}</td>
                   <td class="no-break-cell">{safe(row.get('reference', ''))}</td>
                </tr>
                {{% endset %}}
                {{% set _ = rows.append(block) %}}
                {{% endif %}}
                """)                
        
        if row.type=='text':
            parameters.append(f"""
                {{% if echo.{safe(row.code)}!='0' and echo.hide_{safe(row.code)}!="1" %}}
                {{% if not tab_heading.shown %}}
                  {{{{ tab_heading.heading | safe }}}}
                  {{% set tab_heading.shown = true %}}
                {{% endif %}}""")  
            if table==0:
#                parameters.append('<table>')
                table=1
            parameters.append(f"""
                {{% set block %}}
                <tr>
                    <td>{safe(row.parameter)}</td>
                    <td colspan="3">{{{{ echo.{safe(row.code)} }}}}</td>
                </tr>
                {{% endset %}}
                {{% set _ = rows.append(block) %}}
                {{% endif %}}
                """)
            
        if row.type=='select_one':
            parameters.append(f"""
                {{% if echo.{safe(row.code)}!='0' and echo.hide_{safe(row.code)}!="1" %}}
                {{% if not tab_heading.shown %}}
                  {{{{ tab_heading.heading | safe }}}}
                  {{% set tab_heading.shown = true %}}
                {{% endif %}}""")  
            if table==0:
#                parameters.append('<table>')
                table=1
            parameters.append(f"""
                {{% set block %}}
                <tr>
                    <td>{safe(row.parameter)}</td>
                    <td colspan="3">{nl.join([f"{{{{  '{choice[1]}' if '{choice[0]}'== echo.{safe(row.code)} else '' }}}}" for choice 
                      in [option.split(' | ') for option in row.choices.split(' / ')]])}</td>
                </tr>
                {{% endset %}}
                {{% set _ = rows.append(block) %}}
                {{% endif %}}
                """)
            
                
        if row.type == 'textarea' and column==1:
            if table==1:
                table=0
                parameters.append("""
                {% if rows %}
                    <table>
                       {{ rows | join('\n') | safe }}
                    </table>
                {% set rows = [] %}
                {% endif %}""")
            parameters.append(f"""
                {{% if echo.{safe(row.code)}.strip()!=''  and echo.hide_{safe(row.code)}!="1" %}}
                {{% if not tab_heading.shown %}}
                  {{{{ tab_heading.heading | safe }}}}
                  {{% set tab_heading.shown = true %}}
                {{% endif %}}  
                <div class="description {"columns" if column > 0 else ""}">
                    {{{{ echo.{safe(row.code)} }}}}
                </div>
                {{% endif %}}""")
            
            
        if row.type == 'rte':
            if table==1:
                table=0
                parameters.append("""
                {% if rows %}
                    <table>
                       {{ rows | join('\n') | safe }}
                    </table>
                {% set rows = [] %}
                {% endif %}""")
            parameters.append(f"""
                {{% if (echo.{safe(row.code)} | striptags | trim ) != '' and echo.hide_{safe(row.code)}!="1" %}}
                {{% if not tab_heading.shown %}}
                  {{{{ tab_heading.heading | safe }}}}
                  {{% set tab_heading.shown = true %}}
                {{% endif %}}  
                <div class="description {"columns" if column > 0 else ""}">
                    <span id='{safe(row.code)}'>{{{{ echo.{safe(row.code)} | safe }}}}</span>
                </div>
                {{% endif %}}""")
                              
        if row.type=='other_starts_with':
            if table==1:
                table=0
                parameters.append("""
                {% if rows %}
                    <table>
                       {{ rows | join('\n') | safe }}
                    </table>
                {% set rows = [] %}
                {% endif %}""")

            parameters.append(f"""
                {{% if (echo.{safe(row.code)} | striptags | trim ) !='' and echo.hide_{safe(row.code)}others!="1" %}}
                {{% if not tab_heading.shown %}}
                  {{{{ tab_heading.heading | safe }}}}
                  {{% set tab_heading.shown = true %}}
                {{% endif %}}  
                <div class="description {"columns" if column > 0 else ""}">
                    <span id='{safe(row.code)}others'>{{{{ echo.{safe(row.code)}others | safe }}}}</span>
                </div>
                {{% endif %}}""")
            
            
#            parameters.append(f"""
#        {{% for key, parameter in echo.items() if key.startswith('{row.code}') and (not key.endswith('_text')) and key not in {[code for code in #codes if code.startswith(row.code)]} %}}
#           {{% set block %}} 
#                 <tr>
#                    <td>{{{{ key }}}}{{{{ parameter.name | translate }}}}</td>
#                    <td>{{{{ parameter }}}}{{{{ parameter.value | translate }}}}</td>
#                    <td>{{{{ parameter.units | translate }}}}</td>
#                    <td></td>
#                </tr>
#            {{% endset %}}
#            {{% set _ = rows.append(block) %}}            
#        {{% endfor %}}
#        {{% if rows %}}
#             <table>
#                   {{{{ rows | join('\n') | safe }}}}
#             </table>
#             {{% set rows = [] %}}
#        {{% endif %}}
#        """)

        if row.type=='other_other':
            if table==1:
                table=0
                parameters.append("""
                {% if rows %}
                    <table>
                       {{ rows | join('\n') | safe }}
                    </table>
                {% set rows = [] %}
                {% endif %}""")
            codes_not_starting_with = codes.copy()
            other_starts.extend(['hide_', 'ref_', '_'])
            for start in other_starts:
                for code in codes:
                    if code.startswith(start):
                        codes_not_starting_with.remove(code)
            parameters.append(f"""
        {{% for key, parameter in echo.items() if (not key.endswith('_text')) and not ({' or '.join([f"key.startswith('{code}')" for code in other_starts])}) 
        and key not in {codes_not_starting_with} %}}
            {{% set block %}}
                <tr>
                    <td>{{{{ key }}}}{{{{ parameter.name | translate }}}}</td>
                    <td>{{{{ parameter.value | translate }}}}</td>
                    <td>{{{{ parameter.units | translate }}}}</td>
                    <td></td>
                </tr>
            {{% endset %}}
            {{% set _ = rows.append(block) %}}            
        {{% endfor %}}
        {{% if rows %}}
             <table>
                   {{{{ rows | join('\n') | safe }}}}
             </table>
             {{% set rows = [] %}}
        {{% endif %}}
        """)


    parameters = '\n'.join(parameters)

    return(parameters)



def html_form_scripts(df):
    
    rows=df.to_dict("records")

    html = []

    formulas = {}
    dependent = []
    dependence = {}
    independent = []
    logic = {}
    dependence_logic = {}
    referenced_variables = []

    table = {}
    tab=0
    tabs=[]

    # preliminary screen of rows to collect formulas, dependence of fields and logic
    for row in [r for r in rows if r['code'].strip()!='']:
        table[row['code']] = row
        if row['calc'].strip()!='':
            # create dict of formulas and reverse dict of dependent fields
            formulas[row['code']] = row['calc'].replace(' x ','*') 
            independent.extend(extract_codes(formulas[row['code']]))
            dependent.append(row['code'])
            for variable in extract_codes(formulas[row['code']]):
                if variable in dependence.keys(): 
                    dependence[variable].append(row['code'])
                else:
                    dependence[variable] = [row['code']]
    # create dict of logics and reverse dict of dependent logics
        if row['logic'].strip()!='':
            logic[row['code']] = row['logic']
            independent.extend(extract_codes(logic[row['code']]))
# added 4.0
#            dependent.append(row['code'])
            for variable in extract_codes(row['logic']):
                if variable in dependence_logic.keys():
                    dependence_logic[variable].append(row['code'])
                else:
                    dependence_logic[variable] = [row['code']]
        if f"{row['upper']}".strip()!='' or f"{row['lower']}".strip()!='':
            referenced_variables.append(row['code'])


    variables = []
    variables.extend(dependent)
    variables.extend(independent)
    variables.extend(referenced_variables)
    independent = list(set(independent))
    variables = list(set(variables))


    
    for variable in variables:
        html.append(f"const el_{variable} = document.getElementById('{variable}');")


## calculate functions

    for variable in dependent:
        arguments = extract_codes(formulas[variable])
        html.append(f"function calc_{variable}({{{', '.join(arguments)}}}){{")
        html.append(f"return {to_js(formulas[variable])}}};")
        html.append("")


## update functions

    for variable in dependent:
 
        html.append("")
        arguments = extract_codes(formulas[variable])
        html.append(f"function update_{variable}(i=1) {{")
        html.append("if (i>5) { logicUpdate(); return 0; }")
    
        html.append("let empty = 0;")

        for argument in arguments:
            html.append(f"if (el_{argument}.value == '') empty = 1;")
            html.append(f"const {argument} = toNum(el_{argument}.value);")
        html.append(f"let step = parseFloat(el_{variable}.step);")
        html.append("if (isNaN(step)) step=1;")
    
        html.append(f"const result_{variable} = calc_{variable}({{{', '.join([f'{arg}: {arg}' for arg in arguments])}}});")
        html.append(f"if (Number.isFinite(result_{variable}) & result_{variable}!=0) {{ el_{variable}.value = roundToStep(result_{variable}, step); }}")
        html.append(f"if (result_{variable}==0) {{ el_{variable}.value = ''; }}")
        html.append(f"if (empty && i>1) {{el_{variable}.value = '';}}; ") ## check that this is not initial update
#        html.append(f"if (result_{variable} == el_{variable}.value) return -1; ")


        html.append(f"refupdate_{variable}()")
        
        for dependent_variable in dependence.get(variable, []):
            html.append(f"update_{dependent_variable}(i+1);")

#        for dependent_variable in dependence_logic.get(variable, []):
#            html.append(
#                f"""if ({to_js(logic[dependent_variable])}) {{
#                  document.getElementById('row_{dependent_variable}').style.display = '';
#                  document.getElementById('hide_{dependent_variable}').value = '0';
#                  }}
#            else {{
#                document.getElementById('row_{dependent_variable}').style.display = 'none';
#                document.getElementById('hide_{dependent_variable}').value = '1';
#                }}
#            """)

        
        html.append("}")

    
        html.append("")


## reference range update
    for variable in variables:
        html.append(f"""
            function refupdate_{variable}(){{""")
        if variable in referenced_variables:
            html.append(f"""
                document.getElementById('ref_{variable}').innerHTML = '';
                if (el_{variable}.value != '') {{
                const value = toNum(el_{variable}.value);
                let ref='';""")
            if (table[variable]['upper']!=''): html.append(f"""
                if (value > {num(table[variable]['upper'])}) ref='+';""")
            if (table[variable]['upper2']!=''): html.append(f"""
                if (value > {num(table[variable]['upper2'])}) ref='++';""")
            if (table[variable]['upper3']!=''): html.append(f"""
                if (value > {num(table[variable]['upper3'])}) ref='+++';""")
            if (table[variable]['upper4']!=''): html.append(f"""
                if (value > {num(table[variable]['upper4'])}) ref='++++';""")
            if (table[variable]['lower']!=''): html.append(f"""
                if (value < {num(table[variable]['lower'])}) ref='-';""")
            if (table[variable]['lower2']!=''): html.append(f"""
                if (value < {num(table[variable]['lower2'])}) ref='--';""")
            if (table[variable]['lower3']!=''): html.append(f"""
                if (value < {num(table[variable]['lower3'])}) ref='---';""")
            if (table[variable]['lower4']!=''): html.append(f"""
                if (value < {num(table[variable]['lower4'])}) ref='----';""")
            html.append(f"""
                document.getElementById('ref_{variable}').innerHTML = ref;
                document.getElementById('inp_{variable}').value = ref;
                }}""")
        html.append("""
            }""")



### on_Input_ functions ###
## activates once on input and pass to dependent update_functions
  

    for variable in variables:
        html.append(f"""
    function onInput_{variable}() {{
        refupdate_{variable}();""")
        # update dependent fields
        for dependent_variable in dependence.get(variable, []):
            html.append(f"""
        update_{dependent_variable}();""")
   
    # update dependent logics (show/hide)
        consts = []
        for dependent_variable in dependence_logic.get(variable, []):
            consts.extend(extract_codes(logic[dependent_variable]))

        for const in list(set(consts)):
            html.append(f"const {const} = el_{const}.value;")
    # $#$#$#$#
        for dependent_variable in dependence_logic.get(variable, []):
            html.append(
                f"""if ({to_js(logic[dependent_variable])}) {{
                  document.getElementById('row_{dependent_variable}').style.display = '';
                  document.getElementById('hide_{dependent_variable}').value = '0';
                  }}
            else {{
                document.getElementById('row_{dependent_variable}').style.display = 'none';
                document.getElementById('hide_{dependent_variable}').value = '1';
                }}
            """)


        html.append("}")
        html.append("")

## Initial logic update ###############################
    
    html.append(f"""
    function logicUpdate(){{""")
    consts=[]
    for key in logic.keys():
        consts.extend(extract_codes(logic[key]))
    for variable in list(set(consts)):
        html.append(f"const {variable} = el_{variable}.value;")
    for key in logic.keys():
        html.append(
        f"""
    if ({to_js(logic[key])}) {{
        document.getElementById('row_{key}').style.display = '';
        document.getElementById('hide_{key}').value = '0';
        }}
    else {{
        document.getElementById('row_{key}').style.display = 'none';
        document.getElementById('hide_{key}').value = '1';
        }}
        """)
    html.append("}")
    html.append("logicUpdate();")
    html.append("")


## Initial calculation of empty fields ###############################
    
    html.append(f"""
    function calcInitial(i=1){{""")
    # update dependent fields
    for dependent_variable in dependent:
        html.append(f"""
        if (el_{dependent_variable}.value == '') {{update_{dependent_variable}()}};""")
#    html.append("if (i<5) {calcInitial(i+1)};")
    html.append("}")
    html.append("calcInitial();")
    html.append("")



## listeners

    for variable in variables:
        html.append(f"el_{variable}.addEventListener('input', onInput_{variable});")

    return('\n'.join(html))


def to_js(expr: str) -> str:
    
    expr=expr.replace('^', '**')
    expr=expr.replace('–', '-')
        
    # 1. Sanitize variable names (optional: validate)
    if not re.fullmatch(r"[A-Za-z0-9_\s()+\-*/%<>=!&|,.']+", expr):
        raise ValueError("Invalid characters in formula")

    # 2. Replace allowed functions with Math.* equivalents
    func_map = {
        "SIN": "Math.sin",
        "COS": "Math.cos",
        "ABS": "Math.abs",
        "SQRT": "Math.sqrt",
        "MIN": "Math.min",
        "MAX": "Math.max",
    }
    for fn, js_fn in func_map.items():
        expr = re.sub(rf"\b{fn}\s*\(", f"{js_fn}(", expr)

    # 3. Replace logical operators with JS equivalents
    # Be careful with order (longer tokens first)
    replacements = {
        "!=": "!=",
        "==": "==",
        "=": "==",    # single '=' is usually '==' in formula logic
        "&": "&&",
        "|": "||"
    }
    # Replace operators surrounded by non-word characters or boundaries
    for op, js_op in replacements.items():
        expr = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(op)}(?![A-Za-z0-9_])", js_op, expr)

    return expr.strip()


def html_total(title='', header='', description='', scripts='', parameters='', style=''):
    form = f"""
{{% extends "record_form.html" %}}

    {{% block parameters %}}
    {parameters}
    {{% endblock %}}
            
    {{% block endscript %}}
    {scripts}
    {{% endblock %}}

"""
    return(form)




def print_total(title='', header='', description='', scripts='', parameters='', style=''):
    html = f"""
    {parameters}
    """
    return(html)
