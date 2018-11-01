{ nixpkgs ? (import <nixpkgs> {}), gmlib ? (nixpkgs.callPackage ../viskar-ops/packages/gmlib.nix {}), MeshTools ? (nixpkgs.callPackage ../viskar-ops/packages/MeshTools.nix {}) }:

with nixpkgs;

(python36.withPackages (ps: with ps; [ numpy pytest gmlib pytest pytestrunner scikitimage MeshTools ])).env
