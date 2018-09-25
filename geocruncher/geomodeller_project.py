def extract_project_data_noTopography(filepath):
    if os.path.islink(filepath):
        filepath = os.readlink(filepath)
    filepath = os.path.realpath(filepath)
    tree, ns = mx.parse_and_get_ns(filepath)
    root = tree.getroot()
    ns['geo'] = mx.extract_namespace(ns['geo'])
    ns['gml'] = mx.extract_namespace(ns['gml'])
    box = read_box(root, ns)
    faults_data = read_faults_data(root, ns)
    pile = read_pile(root, ns)
    project_directory = os.path.split(filepath)[0]
    return box, pile, faults_data
  
