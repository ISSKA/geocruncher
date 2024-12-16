import os
import subprocess

def main():

    base_dir = 'geocruncher_outputs_topo_reader_after'

    for folder in os.listdir(base_dir):
        folder_path = os.path.join(base_dir, folder)
        if os.path.isdir(folder_path):
            print(f'Profiling {folder}')
            command = [
                'python', 'geocruncher/topography_reader.py',
                os.path.join(folder_path, 'intersections_dem.asc')
            ]
            subprocess.run(command)

if __name__ == '__main__':
    main()